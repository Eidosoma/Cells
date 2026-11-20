# Can a checksummed Lean proof let Cells stop re-testing a source file? A read-only study

*Placed in `lean/docs/` on 19 November 2026 at the owner's direction. This is the report of a
read-only study made that evening, at the owner's request, by an agent working for the viewer's
lane: could a checksummed Lean proof of a source file let the engine stop re-testing that file?
It is a study with options and a recommendation. Nothing in it is decided, and nothing was built
or changed. Before it was relayed, the viewer's coordinator checked these of its claims against
the files at `15efb14b`: the failed insertion-heat check and the code lines it names,
`constant_field.py` as a declaration only, the eight laws that name no kernel (in the manifest
written at `1ca5eada`), the tier file's counts, the decisions cited, and that `gate-fail-fast` is
not in main. Its estimates (the 9 to 15 per cent, the shares of compile time, the count of stale
comparisons) and what it says of outside tools were not derived again. The text is the study's
own but for this note, one checkout's path taken out, and the five statements written out in the
section "Checks of five statements the study was given".*

19 November 2026, evening. Everything below was read at revision `15efb14b`, in a clean checkout of main made for the
study. Nothing was built, run or changed.
The scratch scripts and their outputs are in `/mnt/workspaces/Cells/visualizer-analysis/lean-tests-20261119/`.

"Processor-seconds" (proc-s) means the sum of each test file's recorded seconds in
`tests/test_tiers.json`. Each file runs on one CPU. Tiers 1 and 2 hold 597 files and 10,534 proc-s
(175.6 processor-minutes). The earlier review measured a full gate at about 41 minutes of checking,
of which tiers 1 and 2 take 24–27.5 minutes of wall time on one lane. Gates waited a median of
49 minutes for a lane.

## The answer

**No, not as asked. A narrower form is possible, and it saves little time.**

A Lean proof at this revision is about a formula written in Lean over the real numbers. It is not
about the Python file. A checksum of the file would certify a property that the code is not shown
to have. This has already happened once: `membrane-insertion-heat` is proved in Lean. The code
computes the same two-term heat expression in float64, and at an extreme input it gives
−0.043 pJ where the theorem guarantees a non-negative value (`lean/claims.json:565`,
`src/cells/models/pump_composite_adapter.py:994-995`).

What works needs no proof at all: **skip a test while nothing it depends on has changed.** That is
a cache keyed by content. D229 has already approved it for landings that change nothing under
`src/`. For landings that do change `src/`, the engine's import hub limits it to an estimated 9–15%
of tier 1–2 time.

What a proof adds on top is small. With a correspondence check standing in (the code compared
with the proved formula on a stated domain), a proof could let a few property assertions be retired
for good. Those assertions sit inside test files that still compile the same worlds, so the saving
is a few seconds per gate. Most of the gate's cost is compiling worlds (about 48% of tiers 1 and 2,
by the testing plan's extrapolation from a 14-file sample), and no theorem about a single law
touches that.

The proofs are worth having for what they find, not for the test time they save. They have
already found a floating-point failure and a sign interval that the engine's docstring missed.

## The options at a glance

Savings are per gate, in the tier file's own seconds. They are estimates where marked; §F says how
each was counted.

| # | Option | What it saves | Cost to build and keep | How it goes wrong, and how that is noticed | Needs |
|---|---|---|---|---|---|
| 0 | *Context, not an option here:* the persistent JAX compilation cache (D229 item 1, under qualification) | Compiling is about 48% of tiers 1 and 2, and 56% of tiers plus G1 (testing plan §4.4: an extrapolation from a 14-file sample and two G1 items). On a full cache hit, compile cost fell to about 5% of a cold compile (measured on two items). | Already being built | Not bitwise identical. Its qualification is designed for this. | Nothing from Lean |
| 1 | **Results keyed by content, no Lean:** D229's scope map (built on branch `gate-fail-fast`, not on main), extended to landings that change `src/` | Landings with no `src/` change: tiers fall from about 27.5 to 3–5 minutes (plan's estimate). Landings that change `src/`: about **9–15%** of 10,534 proc-s, i.e. 970–1,580 proc-s, or 2–4 minutes of wall time *(an estimate from static import closures over the last 40 `src/` landings; neither end is a bound, and the recorder's first nightly map replaces it)* | Days. The recorder, map and selection exist. Missing: a selection rule for `src/` changes, the environment in the key, and a shadow mode. | A skipped test whose unrecorded input changed (a child process, an environment variable, the machine). Noticed by the nightly full run (D229 rule 3) and by shadow comparisons. | Lead: tooling. Owner: amend D223/D229's "a `src/` change keeps the full gate". |
| 2 | **A proof bound to a law's files:** a generated record per claim holding the theorems, the Lean and Mathlib pins, the comparison's engine revision, the files it exercised and the check's result | **Skips:** nothing beyond option 1. **Retires:** no whole test file. A few assertions in about four test functions in `test_surface_transport.py` and `test_kinetic_pump.py`: well under 10 proc-s *(estimate)*, with an upper bound of 45.6 proc-s (0.43%) for the two whole files. | Small: a generator script and a check. Keeping it current is the Lean project's work. | A file binding misses the kernel. For 8 of 28 laws the manifest names no kernel at all, and for `constant_field@1` the law's file is a declaration only. The binding also goes stale quickly: within hours, 11 of 14 engine comparisons had a changed source file. And it can give false confidence: membrane insertion is proved but failed its check. Noticed only if the record carries the numerical status and its domain. | Lean project: the generator. Lead: kernels declared for every law. Owner: whether a proof plus a check may replace a test (D187 rule 6), and the hash form. |
| 3 | **One source for a formula:** generate the Lean definition and the JAX kernel from one description, or translate the traced JAX program into Lean and prove it equal to the proved definition | No test time by itself. It removes hand transcription (`IonChannels.lean` and `JunctionGate.lean` retype engine parameters). | Weeks. No Lean 4 tool emits JAX. A translator from traced JAX programs (jaxprs) to Lean real arithmetic for about 15 element-wise operations is feasible. Loops, scatters and solves are much harder. | Real arithmetic still. Floating-point failures pass as before. | Lean project and lead jointly |
| 4 | **Floating point:** a stated error bound or domain of validity per kernel, checked against the compiled program | The same few assertions as option 2, but "proved" would then hold for what the code computes on domain D. It would have flagged the membrane-insertion cancellation (condition number about 10¹⁶). | Days per closed-form kernel (Bernoulli factor, lag weight, logarithmic mean, insertion heat). Iterative solves are a research project. Lean 4 IEEE libraries (Flean, FloatSpec) are early. | The XLA compiler may reorder floating-point operations, and its `exp`/`log` accuracy has to be assumed, not proved. | Lean project, plus a numerics owner |
| 5 | **Proofs of invariants above a single law** (a ledger closing over a step, composed operators) | **None** of the world tests in any foreseeable time. The existing theorems are about abstract finite graphs, not about the step code's scatters, masks, padding and tolerances. | Months, and it needs option 3 for array code first. | None to monitor; this is a statement of limits. | n/a |

## Recommendation and the first trial

1. **Do not build "never test again because a checksum matches".** The proofs do not reach the
   code, and a file checksum does not reach the kernel the code actually runs.
2. **Take the time savings where they are, with no Lean in them:** the compilation cache (0), then
   option 1. Land the scope map that already exists, then extend it to `src/` landings in shadow
   mode first.
3. **Build option 2 light, as a staleness flag, not as a skip.** Use a generated record that
   needs no new hash: the comparison's engine revision is already in `lean/claims.json` (for
   example `lean/claims.json:9`), and `git diff --quiet REV HEAD -- <files>` tells whether the
   checked code has changed. This gives the Lean project a re-check queue, and it is the
   precondition for any later retirement.
4. **Try option 4 on the closed-form kernels as research.** It is the only route by which
   "proved" could ever be said of what the code computes.
5. **Option 3 only if option 2 shows transcription drift. Option 5: no.**

**First trial: `constant_field@1` (gap-junction flux), in shadow mode, for two weeks.**
- **Why this law:**
  - Three proved claims rest on it.
  - Its kernel is pure and stable. `src/cells/laws/junctions/selective.py:19` and the Bernoulli
    factor at `src/cells/laws/electrochemistry.py:17` are unchanged since the comparison's
    revision `109a7355`.
  - Its kernel-level test builds no world: `tests/unit/test_surface_transport.py`, tier 2,
    41.72 proc-s, 34 tests. Its module-level import closure is only 15 files.
  - Two of that file's tests overlap with theorems: the reversal assertions
    (`flux_reverse`, which also covers face flux through `Face.flux_reverse`) and the blocking
    assertions (`flux_blocked`). Both tests also check more than the theorems state (§A).
- **Steps:**
  1. Generate the binding record: the theorems, the Lean and Mathlib pins, revision `109a7355`,
     and the four exercised files.
  2. At every landing and every night, compute "would skip" under option 1 (the file's recorded
     runtime closure) and under option 2 (the binding unchanged). Still run the file, and record
     whether its outcome matched.
  3. Run the file once with pytest's `--durations=0`, to get the seconds of the reversal and
     blocking tests and of their shared compiled fixture.
- **What it measures:** the hit rate and the false-skip rate of each key, at no risk, plus the
  exact ceiling of retirement for this law.
- **My expectation (an estimate):**
  - The skip saves at most 41.72 proc-s per hit, about 0.4% of tiers 1 and 2.
  - Retirement saves a few seconds, because both tests read the shared `computed` fixture
    (`tests/unit/test_surface_transport.py:141-185`).
  - If the trial confirms this, stop there for test time and keep option 2 as the staleness flag.

## What "never" can honestly mean

After the recommended design, a test file still runs:
- when any file in its recorded runtime closure changes. For any test that builds a world, that
  includes every law and operator module, because the registries import them all;
- when the test itself, its fixtures or the data it reads change;
- when the Python, JAX/jaxlib, numpy/scipy or BLAS versions change, or the venv changes;
- when the environment changes: the x64 flag and platform are set by the runner, and everything
  else passes through;
- on a new machine or CPU type;
- every night, in full, as the check on the key.

A proof adds one thing to this list. For a property a theorem states, a correspondence check can
take the place of the property test. That holds only while the correspondence check itself
re-runs whenever the code changes, so even then "never" means "not separately".

**Risks left after the recommended design:**
- an input the recorder cannot see (children that clear their environment, reads from inside C
  extensions);
- nondeterminism;
- inputs outside a theorem's domain, and every floating-point effect, until option 4;
- composition, restart, order of accuracy and CPU–GPU agreement, which no theorem here addresses.
  The tiers are CPU-only (`scripts/test_tiers.py:150-158`).

## What the owner must decide

1. **The hash form.** The rule is at `AGENTS.md:67-69`: provenance is the Git revision, the dirty
   diff and the frozen snapshot; "do not add per-call or bytecode attestation layers, and do not
   embed SHA-256 hashes of other source files as literals in new code". It came in on 8 November
   (commit `04e399a2`). D185 item 5 restated it as "There is no attestation layer"
   (`docs/DECISIONS.md:5998`).
   - **Inside the rule as written, needing no decision:**
     - (a) No stored hash at all. The binding is a revision plus paths, compared by `git diff` or
       `git rev-parse REV:path` when the check runs. `claims.json` already stores the revisions.
       `git diff` needs a Git checkout; gates run from frozen snapshots, so there (a) pairs with
       (c).
     - (b) Git blob IDs or SHA-256 computed when a tool runs and written to a generated,
       untracked cache record. This is what `scripts/gates/fingerprints.py:27-29` (`identity`,
       "git blob ids, computed here"), the scope map and the viewer's test cache do.
     - (c) The frozen snapshot's own per-file digests.
   - **Needing the owner's word:**
     - (d) File hashes committed into a tracked register such as `claims.json` or a Lean file,
       which a gate then trusts in order to skip tests. It is not "code", but it works as an
       attestation layer.
     - (e) Any check of a file's hash at import or per call.
     - (f) Keys over bytecode or normalized syntax trees. These would ignore docstring edits like
       the one that changed `src/cells/laws/transport/proton_leak.py` in `603345f7`.
   - **I recommend (a).**
2. **Whether `src/` landings may run a selection.** D223 rule 2 and D229 rule 3 say a `src/`
   change keeps the full gate (`docs/DECISIONS.md:7185-7186`, `7438`). Option 1 for those
   landings needs that amended, with the nightly run kept.
3. **Whether a theorem plus a correspondence check may stand in for a test.** D187 rule 6
   (`docs/DECISIONS.md:6046`) says each claim keeps its independent reference, its planted
   control and its conservation checks. Retirement under options 2 or 4 needs the owner's explicit rule.
   The recommendation does not need it.
4. **Ownership of the record.** `lean/` is an independent agent's project. Decide whether the
   binding record lives there, made by its generator, or in the engine's gate tooling.
5. **Whether the Lean numerical checks join a gate.** Today no gate runs them: the tiers cover
   `tests/` only. They were last run at revisions from 13:02 to 16:55 UTC on 19 November.

## What the engine's lead and the Lean project would each do

**The engine's lead (tooling, if the owner agrees):**
- land `gate-fail-fast`'s scope map and nightly;
- add the environment and the machine to the map's key, or scrub the runner's environment;
- run selection for `src/` landings in shadow mode, and report the hit and miss rates;
- declare `kernels` for the 8 laws whose declaration lists none, so that a binding can name the
  code that computes each law;
- run the trial's `--durations` measurement.

**The Lean project:**
- generate the binding record from `claims.json`'s comparisons, listing the files each check
  exercised;
- state each claim's numeric domain and floating-point status;
- refresh `lean/registry.json`. It lists 28 laws and 22 operators, while `15efb14b` declares at
  least `inward_rectifier_linear_driving_force@1`, `na_anion_symport_factored@1` and
  `population_unit_turnover@1` beyond those (by reading the loaders, not by running them);
- treat the test modules its drivers import as part of their inputs: 10 of the 16 driver scripts
  under `lean/checks/` import from `tests`;
- if the owner wants option 4, start with the closed-form kernels.

---

# Supporting detail

## A. What a proof of each law certifies

**Counted from the register.** `lean/claims.json` has:
- 23 claims, 22 of them proved, naming 92 distinct theorems;
- 22 of the 28 laws and 3 of the 22 operators in `lean/registry.json` covered directly
  (`lean/COVERAGE.md:9`, `:44`);
- 22 numerical checks with status "checked" and 1 "failed".

`lake build` treats warnings as errors (`lean/lakefile.lean:7`), so no `sorry` survives.
`lean/scripts/CheckClaims.lean:14-22` checks only that each named theorem exists in the module the
register names. Whether the claim's prose matches the theorem is reviewed by people.

**Common to every row:**
- Every Lean definition is restated by hand over ℝ. Nothing in `lean/` reads the Python.
- Constants and units are kept abstract: `scale` stands for area × permeability × opening ÷
  mol/fmol (`lean/CellsProofs/Transport/ConstantField.lean:32-37`).
- No theorem says anything about the law's registration or declared fields, about vectorisation,
  masks or padding, or about what the file imports.
- Every numerical check ran on CPU, in float64, at one engine revision.
- Of the 16 driver scripts under `lean/checks/` (not counting `test_claim_docs.py`), 13 build or
  run an engine world and 10 import test modules or test fixtures (§D2).

**How the table was made.**
- I read the statements of all 16 Lean files: the definitions and every public theorem's
  hypotheses and conclusion, not the proof steps.
- I read one driver in full (`constant_field.py`), the others by a mechanical scan (run calls,
  imports, tolerances).
- The "numerical check" column comes from the `result` text in `lean/claims.json`.
- Marks: (F) = floating point not covered; (B) = an engine branch modelled and covered in ℝ;
  (W) = the theorem holds for a wider family than the code, so it cannot detect a wrong choice
  within that family.

| Law(s) | What the theorems cover | What the numerical check covers | What neither covers | Engine tests on the same property | Engine tests on what no theorem states |
|---|---|---|---|---|---|
| `constant_field@1` (3 claims) | Reversal, the value at zero voltage, flow down the gradient, blocking. **(W):** all four hold for *any* factor with eval 0 = 1 (`ConstantField.lean:16-18`, `:40-60`), so they cannot detect a wrong Bernoulli factor. The series branch is defined (`:26-29`) but no theorem is specific to it. | `lean/checks/constant_field.py`: the jitted surface kernel on the "gradient" fixture against the independent reference at protocol tolerances, plus one closed tissue world that calls a test function. | (F); the boundary \|x\| = 10⁻⁴; the law module is a declaration only (`src/cells/laws/routes/constant_field.py:10-19`), while the kernel is `selective.py:19` and `electrochemistry.py:17`, and booking is in `numerics/surface_transport.py` | `test_surface_transport.py::test_patch_subdivision_route_reversal_and_padding` (reversal) and `::test_equilibrium_and_transport_blocking`, which asserts *exact* float zero, stronger than the theorem | The same file's capacitor divider, gauge change, reservoir reset, invalid layouts, domain refusal, batch replay, corrupted accounting, CPU–GPU saved values |
| `junction_voltage_relaxation@1` | Target bounds and monotonicity, the exact relaxation at constant voltage, polarity, composition of two intervals. No branches. Parameters are retyped as literals (`JunctionGate.lean:15-24`). | 45 constant-voltage samples within 1.12 × 10⁻¹⁶; three tissue pairs through a block | (F); voltage changing within a step; the availability multiplier | none declared (manifest `test`: null) | 2 tier-1 files mention it (15.0 proc-s) |
| 6 Kv1, Kir2.1, NaV1.2, K and Na leaks (2 claims) | Gate targets in [0, 1] at every voltage; positive time constants on −120 to +60 mV; the exponential stage keeping [0, 1] including its small-z series (B) (`ChannelStep.lean`); flux scaled by opening and bounded by the fully open flux; off-ions and blocking give zero. NaV rates use the series Bernoulli factor (B) with retyped literals (`IonChannels.lean:46-49`). | 25 voltages, 72 stage cases, a tissue membrane with all ten | (F) (the engine's own comment estimates the series' truncation at 3 × 10⁻¹⁵, `src/cells/numerics/exponential_gates.py:30-33`); the tissue integrator | `test_kv1_channel_laws.py` (tier 1, 9.31 proc-s) checks *correspondence* with references, not the bounds | dispatcher, declaration and registry tests |
| `clleak_always_open@1` | Current sign, and reversal on the regular branch and at zero only (the theorem's `branch` hypothesis); the small branch "follows the implemented polynomial ratio" | Two tissue trajectories, opposite currents | (F); the reversal on the small branch | none | `test_chloride_leak_law.py` (tier 1, 3.25 proc-s): registration, parsing, equality with a chloride patch |
| `passive_neutral_permeation@1` | Fick's form, direction, and the instantaneous gradient rate of a closed pair. (W): any normalized factor. | 5 cases within 7.11 × 10⁻¹⁵; a 20 ms closed pair at relative tolerance 5 × 10⁻⁴ | (F); integration over time | none | `test_passive_routes_kind.py` (tier 2, 52.38 proc-s): exact heat over time, raw-sum bounds, refusals |
| `proton_constant_field_leak@1` | Both evaluator branches in ℝ (B), reversal, analytic heat ≥ 0. It *found* that the polynomial branch moves the reversal ratio, so heat ≥ 0 holds only to rounding. | 12 cases against a 70-digit reference; one 4 ms buffered cell | (F) (accepted by the lead to a tolerance); free versus total H⁺ is checked only numerically | none | the passive-routes and proton-buffer kinds' tests |
| `proton_atp_…@1`, `atp_driven_transporter_…@1` | Net rate J⁺(1 − e^(ΔG/RT)), direction, stall, heat ≥ 0, neutral cargo independent of voltage. The product of capacity, availability and saturation is folded into one logarithm. | 92 tissue states against frozen references (7.50 × 10⁻¹⁶) | (F); the saturation factor's form | `test_atp_transporter.py::test_zero_at_static_head_and_reversal_beyond` (tier 1 file, 1.37 proc-s) | `test_cycle_kind_references.py` (tier 1, 12.41 proc-s: correspondence, Wegscheider band, admission, charge) |
| `nak_atp_…@1`, `ca_atp_…@1` | Stall voltages, direction, net charge per cycle, cancelling currents | 5 voltages against 80-digit references; a 1 ms run | (F) | `test_kinetic_pump.py::test_forward_reverse_scalar_law_and_second_law`, `::test_stall_and_positive_interior_gradient` (file: tier 1, 3.88 proc-s) | the same file's broadcast, vmap, domain refusal and tiny-saturation tests |
| `logmean_electrodiffusion@1` (2 claims) | Both log-ratio branches and the series mean in ℝ (B), reversal, equilibrium, dissipation ≥ 0, the 0.001 unit factor | Includes an adjacent-float pair: CPU gave 0, the reference 1.42 × 10⁻¹⁸ | (F) | none on the engine. `test_surface_reference.py` tests the *reference*. | surface tests |
| `rapid_binding@1` | The equilibrium occupancy c/(K_d + c) | 13 manufactured states within 3.33 × 10⁻¹⁶ | The engine's iterative solve and its convergence; (F) | none | `test_rapid_binding_kernel.py` (tier 1, 8.6 proc-s, 69 tests): solver, margins, iteration count |
| `reservoir_exchange@1` (2 claims) | Rates, normalisation, mean-field drift, the heat of each event | 165 compositions against rational values; 357 pairs; two seeded lineages | (F); stochastic event selection | `test_assembly_lineages_kernel.py::test_kernel_matches_the_oracle` (correspondence) | lineage tests |
| `local_species_reactions@1` (operator; 2 claims) | A weighted inventory is preserved for *any* real extents (W, by design); enzyme and substrate balances | One closed-enzyme half-step, residual 1.12 × 10⁻²⁰ against a tolerance of 6.94 × 10⁻¹⁸ fmol | (F); how the extents are computed | `test_species_reactions_halfstep.py::test_the_bookings_are_exact_on_random_states` checks float exactness, more than the theorem | rates, closed forms, refusals |
| `scheduled_membrane_insertion@1/@2` (operators) | Network heat = a sum of squares ≥ 0; the one-patch formula; zero image charge (`MembraneInsertion.lean:41-65`) | **Failed:** −0.043037 pJ against +0.051603 pJ at ΔC/C = 1.7 × 10¹⁶ | The code adds two terms of about ±8.77 × 10¹⁴ pJ (`pump_composite_adapter.py:994-995`), where float64 spacing is 0.125 pJ | `test_membrane_insertion.py::test_one_patch_analytic` at relative tolerance 10⁻⁹ on ordinary ratios: it passed | onset, padding, refusals, v1/v2 parity |
| General accounting (3 claims, no law) | Finite-graph transfer balance and a split step's regional balance (`Accounting/Transfer.lean`, `Tissue/ReactionTransport.lean`) | The junction ledger and a 12-compartment chain | All of the code's bookkeeping | `test_surface_pump_v3_imex.py` (tier 3, 497.49 proc-s) and `test_species_reactions_composition.py` (tier 3) | n/a |

**Not covered by any proof:**
- 6 of the 28 laws in the registry (the two GARD laws, `ideal_mixing`, `regular_mixing`,
  `stochastic_mass_action`, `transition_state_factor`);
- 19 of its 22 operators;
- at `15efb14b`, also two laws and one operator the registry does not list yet:
  - `src/cells/registry/model_table.py` names 23 law modules under `cells.laws`, including
    `inward_rectifier_linear_driving_force` and `na_anion_symport_factored`;
  - `src/cells/operators/population_unit_turnover.py:106` and `:709-710` declare
    `population_unit_turnover@1` on an `Operator` class, which the operator loader's rule
    (`src/cells/registry/operators.py:250-275`) registers. I read this; I did not run it.

**Where the law's file is not the law's code.** The declarations manifest exported at `1ca5eada`,
54 commits before this revision (`/mnt/workspaces/Cells/visualizer-analysis/declarations-1ca5eada/`),
lists no `kernels` for 8 of the 28 laws: `constant_field`, `logmean_electrodiffusion`, the three
leaks, `passive_neutral_permeation`, `proton_constant_field_leak` and `reservoir_exchange`. For
these, a checksum of `module_path` would bind a declaration, not the computation. The kernel object
format exists (`docs/library/DECLARATIONS_FORMAT.md:150-160`).

## B. When skipping a test is sound

"These inputs have not changed" implies "the outcome would be the same" only if the key holds
everything the outcome depends on.

**What the key must hold:**
- **The code:**
  - the test file;
  - its runtime import closure, including the registry loaders. `_load_builtins` imports every
    model's law homes on first use (`src/cells/registry/laws.py:672-688`), and the operator
    registry imports every module of `cells.operators` (`src/cells/registry/operators.py:263`,
    `:330`);
  - every file it opens or lists, including fixtures, frozen references and JSON protocols;
  - the inputs of its child processes.
- **The interpreter and libraries:** Python, jax, jaxlib (which contains XLA), numpy, scipy and
  its OpenBLAS, pytest and its plugins. In practice, the venv's identity.
- **The environment:**
  - The runner sets `PYTHONPATH`, `CUDA_VISIBLE_DEVICES=""`, `JAX_PLATFORMS=cpu`,
    `JAX_ENABLE_X64=1` and the two output roots (`scripts/test_tiers.py:150-158`).
  - It passes the rest of `os.environ` through. So either the key covers the environment
    (`XLA_FLAGS`, thread variables, `CELLS_*` switches) or the runner must scrub it.
- **The machine:**
  - The CPU model and its instruction set. XLA generates CPU code for the host. This is general
    knowledge, not checked here.
  - The project already treats thread count as an input that changes bits: it pins BLAS to one
    thread at `import cells` (`src/cells/__init__.py:5-8`, D190).
- **Seeds:** 54 test files mention a seed or random generator. I did not check that each one is
  seeded.
- **The compilation cache, once adopted:** its state must not change bits. That is what its
  qualification is for.

**Which tests are closed enough.**
- **Evidence of determinism:**
  - The earlier review found no numerical flakiness.
  - All 39 crossrev and 43 G1 comparisons over 17–19 November were identical.
- **Evidence on closure,** from D229's replay on a 74-file sample (testing plan §10.8,
  `/mnt/workspaces/Cells/testing-plan-20261119/PLAN.md:1411-1449`):
  - 73 files had complete map entries;
  - 7 had child processes the map cannot see;
  - 35 read the repository's own files;
  - `test_gates_lane_busy.py` kills a child it started, so it is always selected.
- **To exclude from any skip:**
  - time-bounded tests;
  - tests whose children are unmapped;
  - tests with conditional skips. 17 tier-1/2 files record skipped tests, 155 in all; I did not
    check why each one skips.

**What D229 already supplies.** It is on branch `gate-fail-fast` (head `98986c26`), not on main.
- **The recorder** (`scripts/gates/scope_inject/sitecustomize.py`) records `sys.modules` at exit,
  an audit hook on `open`, and children's path arguments.
- **The map** (`scripts/gates/scope.py`, `cells.scope_map@2`) records, per test file:
  - content dependencies, by the snapshot's SHA-256;
  - existence questions;
  - folder listings.
- **The selection** compares each dependency with the map's snapshot. It refuses on any `src/`
  change, on a map older than 36 hours, on another interpreter, or after an unexplained nightly
  failure.
- **What is missing for `src/` landings:**
  - a selection rule for them;
  - the environment and machine in the key;
  - a shadow mode.

**The hub, measured.**
- I used the replay's runtime map (`replay-e/map.json`), built on main `b848b5ea` (38 commits
  before `15efb14b`) plus the tooling. It is a 74-file sample, and its own verdict is "failed",
  as the plan says it is by design.
- I counted only dependencies whose recorded state is a file. In that map, every sampled file
  that imports the runner (10 of 10) depended on 43–61 of the map's 61 law modules and 21–22 of
  its 22 operator modules.
- `_load_builtins` loads the 23 law homes the model table names; the other law modules arrive
  through ordinary imports.
- So for any test that builds a world, editing nearly any law or operator file, even its
  docstring, changes its key.

**What the nightly full run is then for:**
- catching what the key missed (an unrecorded input, nondeterminism);
- refreshing the map;
- keeping the recorded outcomes honest.

D229 rule 3 already says a nightly failure stops selection until it is explained
(`docs/DECISIONS.md:7430-7438`).

## C. What a proof adds to a content key

**Retire or shrink for good.** This applies to a property assertion whose statement is a theorem's
conclusion, and only when three things hold:
1. a correspondence check ties the code to the proved definition on the theorem's domain;
2. the floating-point margin is accounted for;
3. the correspondence check re-runs whenever its code changes.

I classified the cited test files by reading their test functions:
- **No whole test file** consists only of such assertions.
- The candidates are a few assertions in four functions:
  - reversal and blocking in `test_surface_transport.py`;
  - direction and stall in `test_kinetic_pump.py`;
  - perhaps `test_atp_transporter.py::test_zero_at_static_head_and_reversal_beyond`.
- Their files keep their shared compiled fixtures, so removing them saves close to nothing and
  changes the files' recorded pass counts.
- Most of the engine's law tests are themselves *correspondence* tests: code against an
  independent reference with a planted error (D187 rule 3). A theorem cannot replace these,
  because they are what links the code to the formula.

**Only skip while nothing changes.** Everything else. That needs no proof.

**Neither:**
- **World runs:** the integrator, composition, refusals, step bookings.
- **Ledgers over a whole step:** the theorems are about abstract graphs; the code's ledgers close
  to rounding, with masks and padding.
- **Composition of operators.**
- **Restart.**
- **Order of accuracy:** the theorems are about instantaneous rates and exact constant-voltage
  solutions, not about integrators.
- **CPU–GPU agreement.**

D187 rule 1 already records why composed worlds are needed: "the raw-sum bound and the cycle
refusals of 16 November showed up only in composed worlds" (`docs/DECISIONS.md:6036-6038`).

## D. The options in more detail

**1. Content-keyed results.**
- **What it is:** the scope map, with a selection rule for `src/` landings. The rule is: run a file
  when any recorded dependency differs from the map's snapshot, with the always-run set and the
  nightly kept.
- **Finer keys** would beat the hub:
  - per function, as pytest-testmon does with coverage;
  - per traced program, the jaxprs crossrev already compares (`scripts/gates/crossrev_sets.py:1-12`).
- For world tests, a program-level key mostly duplicates what the compilation cache gives, because
  compile dominates. So I would not build it before the cache's qualification.
- **Precedent:** the viewer's `npm run test:quick` (`visualizer/tests/lib/test_cache.mjs` on branch
  `visualizer`, `44ab3a0f`):
  - it fingerprints contents, tool versions and environment variables;
  - a missing input is a miss, never a pass;
  - it records only "passed", in an untracked cache;
  - `npm test` never consults it.

**2. A proof bound to files.** Measured on the register as it stands (`scripts/churn.py`, output
`out/churn.json`):
- The 14 engine comparisons name 55 (comparison, file) pairs over 46 distinct `src/` files.
- By `15efb14b` (20:48 UTC), **11 of the 14** comparisons had at least one named file changed since
  their engine revision. Those revisions date from 13:02 to 16:55 UTC.
- The changes were mostly in host files:
  - `surface_pump_v3.py`, 57 commits in the 7 days before this revision;
  - `pump_composite.py`, 45;
  - `pump_composite_adapter.py`, 27;
  - `kinds/transporter.py`, `kinds/passive_routes.py` and `operators/species_reactions.py`.
- Only 2 of the 29 rows under `src/cells/laws/` changed. One was a docstring edit prompted by the
  proton-leak proof itself.
- **Consequences:**
  - A binding on law files alone would rarely be invalidated, but it would miss the code that
    computes and books the law.
  - A binding on everything the check exercised would go stale within hours. That is right for a
    re-check queue and useless for skipping.
- **The drivers depend on the tests:** 10 of the 16 driver scripts under `lean/checks/` import
  from `tests`. For example, `lean/checks/constant_field.py:11-13` imports a test function, and
  `lean/checks/membrane_insertion.py:19-20` imports a test fixture and a test module.
- **The drivers cost what tests cost:** 13 of the 16 build or run a world. `lean/PROGRESS.md`
  records two timings: 9.94 s for the neutral-permeation driver (`:232`) and 13–16 s for two
  runs of the proton-leak driver (`:207`).
- So a check in place of a test moves the compile cost; it does not remove it.

**3. One source.**
- **What exists:**
  - Lean 4 has no backend for JAX.
  - SciLean describes itself as a proof of concept.
  - Lean's own `Float` has no formal semantics to reason with (general knowledge, not checked
    today).
  - LeanBET uses one algorithm over ℝ for proofs and over floats for computing, and reports the
    measured discrepancy (`lean/ENGINE_LAW_VERIFICATION.md:11`).
- **Two practical routes:**
  - (a) A small expression language (+ − × ÷ exp expm1 log where) that emits both the Lean
    `def` and the JAX function. This means rewriting kernels.
  - (b) Translation validation: trace the existing kernel to a jaxpr, translate its element-wise
    operations into a Lean term over ℝ, and have Lean prove that term equal to the proved
    definition, at each landing that changes the kernel. This leaves the engine untouched and
    catches retyped constants and branch thresholds.
- **The limits:**
  - (b) stops at `while_loop`, scatter, segment sums and masks: the Newton solve in
    `rapid_binding` and all booking code.
  - Even where it works, it is still real arithmetic.
  - The Aeneas toolchain (Rust to Lean) shows such translation is practical for a whole language,
    but it took a dedicated project.

**4. Floating point.**
- **For a closed-form kernel on a stated domain,** tools in the FPTaylor family compute rigorous
  round-off bounds, and FPTaylor can emit machine-checkable HOL Light certificates. In Lean 4,
  Flean and FloatSpec (a port of Coq's Flocq) are early.
- **Two caveats:**
  - XLA may reorder operations under `jit`. The JAX FAQ shows `log(exp(x))` giving `inf` eagerly
    and `100.0` under `jit`. So a bound must allow for that, or be stated about the compiled
    program.
  - The accuracy of `exp`, `expm1` and `log` must be assumed.
- **A cheaper first form:** a stated domain of validity per claim, for example
  ΔC/C ≤ 10⁶ for the insertion heat. The correspondence check tests the domain's corners, and the
  engine refuses inputs outside it.
- The membrane case is exactly what this catches: a result 10¹⁵ times smaller than the terms it
  is made of.

**5. Invariants above a law.**
- `region_balance` and `whole_inventory_conserved` hold for *any* flux values on *any* finite graph
  (`lean/CellsProofs/Accounting/Transfer.lean`, `lean/CellsProofs/Tissue/ReactionTransport.lean`).
- They certify the bookkeeping's structure, not that the engine's scatter indices, masks, padding,
  held baths and refusal tolerances implement it. The world ledger tests check exactly those.
- **A cheap neighbour (an idea, not costed):** check, when a world is built, that its layout's
  booking matrix has zero column sums. A theorem then covers what that structural check
  guarantees.

## F. The numbers and how they were counted

| Quantity | Value | How |
|---|---|---|
| Tier 1 / 2 / 3 | 420 files, 2,464.5 proc-s (41.1 min) / 177 files, 8,069.9 proc-s (134.5 min) / 217 files, ≥ 20,412.3 proc-s (≥ 340.2 min) | `tests/test_tiers.json`. Tier 3 is a floor: 215 of 217 rows hit the 90 s measuring cap with no outcome. |
| Files cited by the Lean project (claims' sources, README commands, drivers' imports) or by the manifest's `test` field | 22 test files; 18 in tiers 1 and 2 with 309.2 proc-s; 4 in tier 3, including `test_surface_pump_v3_imex.py`, 497.49. Of the 18, four (106.6 proc-s) are cited only for unproved assembly-lineage laws or operators. Dropping those and adding `test_hill_factors.py` (cited in `ENGINE_LAW_VERIFICATION.md:25`) gives **15 files, 205.4 proc-s (1.95%)** tied to proved claims. | read from the files |
| Tier-1/2 files whose text names a proved law's ID or its declaring module | 63 files, 817 proc-s (7.8%); 14 of them, 69 proc-s (0.66%), show no compile or world call in their text | `scripts/law_tests.py` narrow mode. Text match, an upper bound on relevance. It includes guards such as `test_law_modules.py`. |
| The same, also counting shared kernel modules (`electrochemistry`, `surface_transport`, …) | 109 files, 1,647 proc-s (15.6%) | `law_tests.py` broad mode |
| Retirable by a proof (option 2 or 4) | 0 whole files. A few assertions in about 4 functions: **under 10 proc-s** *(estimate)*; ceiling 45.6 proc-s, the two files' totals (0.43%) | per-test seconds are not recorded; measured by the trial's `--durations` |
| Skippable by content key on a `src/` landing (option 1) | median **9.2%** of tier-1/2 proc-s (static closure with imports inside functions) to **15.0%** (module-level imports, plus every law, operator, kind and model module for files reaching the registry or the definitions parser). 74% if the registry's dynamic imports are ignored, which the runtime map contradicts. Neither end is a bound: the first overstates reach through imports in functions that never run, the second may overstate it through the hub approximation, and both miss other dynamic imports. | `scripts/static_skip_all.py` over the last 40 first-parent landings that changed `src/` (`6c501ab3` back to `599b8610`); estimates, to be replaced by the recorder's map |
| The cited kernel-level files on those 40 landings | `test_surface_transport.py` 40/40 and `test_kinetic_pump.py` 35/40 would skip by module-level closure. Only 6/40 would skip if imports inside functions are followed. | `scripts/static_skip.py`; the truth lies between these. None of the cited files is in the 74-file runtime sample. |
| Staleness of the Lean checks | 11 of 14 engine comparisons have a changed named file by `15efb14b` | `scripts/churn.py` |

**Against the whole gate:**
- Even option 1's higher estimate for a `src/` landing (15%) is about 4 of the 41 checking
  minutes.
- The proof-specific saving is seconds.
- The compilation cache's share (48–56% compile) and the lane waits (median 49 minutes) are both
  an order of magnitude larger.

## Checks of five statements the study was given

The study was given five statements at its start and asked to check them. Each is written out
here, with what the study found.

1. *Nothing under `lean/` holds a checksum of a source file: a claim points at a law's ID and a
   place in the source.* **Holds, with two additions.**
   - `lean/claims/incoming/pgi-evidence.md:47` holds a SHA-256 table of three downloaded evidence
     files.
   - Every engine comparison carries 40-hex Git `engine_revision` and `record_revision` values
     (`lean/claims.json:9-10` and the rest). That is a revision binding, from which file identity
     can be derived without storing a hash.
   - The "blob" hits are GitHub URLs.
2. *The proofs are about formulas in real arithmetic, not about the files, and one proved claim's
   numerical check on the engine's code failed.* **Holds.**
   - The membrane case is not a different formula: Lean's `heat` is the same two-term expression
     (`MembraneInsertion.lean:41-42`) that the code computes with a cancellation.
   - A second instance: the proton-leak proof showed the polynomial branch can reverse the heat's
     sign within a relative interval of about 10⁻³³. The engine's docstring was corrected in
     `603345f7`.
3. *The project's rule bars per-call or bytecode attestation layers, and SHA-256 hashes of other
   source files as literals in new code.* **Holds** (`AGENTS.md:67-69`). The forms inside and
   outside the rule are in decision 1 above.
4. *Gates are sized to the change (D223, D229), and the tier file holds 420, 177 and 217 files in
   tiers 1, 2 and 3, at 41.1, 134.5 and 340.2 processor-minutes.* **The counts hold**, with two
   corrections:
   - Tier 3's 340.2 minutes is a floor.
   - D229's selection tool is on `gate-fail-fast`, not on main at `15efb14b`.
5. *The viewer already skips a test file whose inputs have not changed, with no proof in it.*
   **Holds**, except that the viewer's cache is on branch `visualizer` (`44ab3a0f`), not on main at
   `15efb14b`.

Also: the heading "Lean scientific workflow" in `AGENTS.md:104` means *lean* as in light process.
It is not about the Lean prover.

## Sources

All from general web searches. I read **search-result summaries only, not the pages**, so treat
the details as unverified. The 2026 arXiv items especially are unconfirmed.
- **Bazel remote caching** ([bazel.build/remote/caching](https://bazel.build/remote/caching)):
  test actions are keyed by the digest of the executable, runtime dependencies, data files,
  arguments and environment. Reuse across machines is safe only if the build is reproducible.
- **Ekstazi** ([Gligoric's 2015 dissertation, which includes the ISSTA 2015 work](https://users.ece.utexas.edu/~gligoric/papers/Gligoric15PhD.pdf);
  [Celik et al. 2017](https://users.ece.utexas.edu/~gligoric/slides/CelikETAL17RTSLinux.pdf)):
  test selection by dynamic file dependencies. It is unsafe when recorded dependencies miss
  children or native code; one study found it recorded about 17% of the files a system-level
  tracer saw.
- **pytest-testmon** ([pypi.org/project/pytest-testmon](https://pypi.org/project/pytest-testmon)):
  selection by coverage, per method. It does not see data files by default.
- **FPTaylor** ([UUCS-15-001](https://users.cs.utah.edu/docs/techreports/2015/pdf/UUCS-15-001.pdf);
  [TOPLAS 2018](https://api.crossref.org/works/10.1145%2F3230733)): rigorous round-off bounds with
  HOL Light certificates. It struggles with large expression graphs.
- **Flean** ([github.com/minusgix/flean](https://github.com/minusgix/flean)) and **FloatSpec**
  ([reservoir](https://reservoir.lean-lang.org/@Beneficial-AI-Foundation/FloatSpec)): Lean 4
  IEEE-754 formalisations, both incomplete.
- **SciLean** ([reservoir](https://reservoir.lean-lang.org/@lecopivo/scilean)): "a proof of
  concept".
- **Aeneas** ([github.com/AeneasVerif/aeneas](https://github.com/AeneasVerif/aeneas)): translates
  safe Rust into Lean. Its soundness relative to Rust's semantics is stated as future work.
- **JAX FAQ** ([docs.jax.dev/en/latest/faq.html](https://docs.jax.dev/en/latest/faq.html)):
  `jit` can change floating-point results through XLA rewrites. There is no promise that jitted
  and eager outputs are bitwise identical.

## What I did not check, and how the work ran

**Not checked:**
- I ran no engine code, no test and no Lean build. So I have no per-test seconds, and no runtime
  import closures for the cited files (none is in the 74-file sample).
- The skip percentages come from static closures and are estimates with the bounds stated.
- The declarations manifest I read is the export at `1ca5eada`, not `15efb14b`.
- I did not verify that each seeded test is deterministic, or whether XLA's CPU code differs
  between CPU models.
- I did not check whether the membrane-insertion fix has landed after `15efb14b`. At `15efb14b`
  the two-term form is still in place.
- The test-to-law matching is by text and by my reading of test names. I read the bodies of only
  two test functions (`test_surface_transport.py:141-185`).
- I read the Lean proofs at statement level only. I read one driver in full; the others I scanned
  mechanically.
- The compile shares (48%, 56%) and the 5% cache-hit cost are the testing plan's figures, which
  rest on a 14-file sample and two items. I did not re-derive them.

**How the work ran:**
- The analysis scripts (`churn.py`, `law_tests.py`, `static_skip*.py` and the map counts) ran
  pinned to CPUs 12–15 and 28–31 and capped at 4 GB.
- Many small `git`, `grep`, `sed` and `python3 -I -c` reads ran without the pin and cap,
  before and after those scripts.
- One small `python3 -` heredoc (no `-I`) patched my own scratch script.
- I read the testing plan and the replay map under `/mnt/workspaces/Cells/testing-plan-20261119/`,
  and the `gate-fail-fast` and `visualizer` branches through `git show`. I did not read the live
  checkout.
- Two web searches got no verdict from the safety classifier, a transient error. Each was retried
  once, unchanged, and succeeded.
- Nothing was refused.
