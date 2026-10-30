# Held-active array execution

Chief assigned only new `physiology_active_temperature_arrays*` implementation,
reference and test files. Root owns shared documents and transition/initial
preparation work. Existing source investigations and accepted histories remain
untouched. CPU5 status is not inspected or polled.

The array cohort is a new numeric execution port of the explicit
`active_uniform_isothermal_fixed_empirical_kinetics@1` held-rate contract.
`prepare_world` validates exact original model/source/binding owners, original
298.15 K complete state/history/layout and the inherited step/loss criteria.
Each world carries an exact host-certified Kelvin point and maximum rate-view
step. A cohort reconstructs source declarations/bindings and repeats admission,
so a checksum alone cannot substitute for actual original source validation.
Only homogeneous exact model families and typed numeric tree shapes stack;
different owner orders/values remain per-world arrays. Duplicate IDs and mixed
families are refused. Prepared arrays are immutable and cohort records bind
every original source definition, owner binding, numeric state/layout and
temperature/step certificate.

Root's snapshot review identified a device-buffer host-dispatch risk. Complete
source layouts are converted to NumPy immediately after exact layout checking,
before host control construction or validators; state leaves already undergo
the same normalization. Five restart tests use ordinary snapshot IO, confirm
the loader's JAX buffers, and verify host arrays preserve every dtype and anchor
bit before complete NumPy rate/field evaluation. This change is confined to the
new array host boundary; frozen active-temperature-02 evidence is unchanged.

Point certification is deliberate. Runtime T must equal that world's certified
point; another T requires host preparation so it cannot inherit an unrelated
loss/step proof. Runtime controls may vary independently within [0,1]. Host
step bounds are checked with full availability; runtime checks include actual
control domains, all active/chemical/affinity domains, converged fields,
complete finite rates, dissipation, `1e-10 pJ/s` stage energy balance and the
unchanged 5% passive/pool gross-turnover ceilings for the proposed step.
Shape/dtype is a static array protocol, not a dynamic numerical refusal flag.
The control packet's exact family type and every owner-axis shape are checked
before arithmetic; malformed short vectors cannot broadcast across owners.

Pure `project` and `evaluate_world/evaluate_batch` contain no parser, host
validator, host transfer, random draw, history mutation or accepted step. The
numeric projection recomputes maintained Na/K drive, ER T and fixed-J standard
coefficients/reaction differences, plus finite PMCA/ER `-RT ln(1000)` caches.
Existing full physical rate/field kernels supply all 56 supported channel laws,
owned chemistry, plasma/ER/fuel and actual open reservoirs. Native rounded
constant/split-temperature semantics remain separate evidence; the existing
coherent SI kernels and declared maintained/finite standard conventions apply.

Results preserve the exact raw proposed Kelvin scalar, controls and step and
the complete raw projected layout, including nonfinite coefficients. Invalid
input arithmetic is evaluated with certified T, a certified step and (when
needed) zero controls solely to keep its diagnostic path bounded. Those
substitutions are returned explicitly and never make the raw proposal valid.
`reason_validity` lists the named predicates; `reason_mask` sets bit i for each
false predicate. `valid` means the complete held-rate criteria pass; it is not
checkpoint or thermal-step admission. All original arrays/anchors remain
available separately in the prepared numeric cohort.

Validation compares NumPy cohorts to serial host views and independent full
derivatives plus 32 physical field columns. Reorder/partition comparisons cover
every numeric result leaf. Raw invalid T/control/step evidence includes NPZ
arrays and explicit reason bits without JSON sanitizing the raw buffers.
Independent replays deny Cells/JAX/BETSE imports and reconstruct from actual
source declarations and the new point-certificate semantics.

CPU JAX qualification is staged per family: shape tracing, compiled numeric
projection, then lowering/compiling/executing the full two-world RHS/field
function with host validators disabled by test tripwires. All tests retain x64,
the existing rate/charge/potential/field budgets and CPU4/one-thread caps: 1 GiB
summed process-tree RSS, at least 8 GiB host reserve, 480 s per phase. The five
family compile phases may exceed ten minutes in aggregate; that qualification
must launch detached with frozen sources and durable phase logs/failure/result
artifacts. Its status is checked only on a later user/Chief instruction. GPU
execution, accepted stepping, heat, thermal dynamics and guard relaxation are
deferred.

## Requested audit and subsequent source changes

On Chief's explicit detached-outcome audit instruction, saved CPU run01 was
inspected without retry. It failed the summed-RSS guard during the first full
two-world ionic RHS compilation. Shape tracing, projection compilation/execution
and full-RHS lowering completed; full compilation/execution and all complete
compiled reference comparisons did not. Observed RSS/HWM was 1,082,802,176 bytes
(1,032.640625 MiB), versus 1,073,741,824 bytes, at 19.65 s; final phase receipt
was 19.78 s. Minimum host memory reserve was 20,601,839,616 bytes. This was the
declared guard's stop, not an observed host-memory exhaustion or scientific
domain failure. No phase was completed, and no CPU JAX RHS parity is claimed.
The independent source/runtime failure audit is
`active_temperature_arrays_cpu01_failure_audit.json`; frozen inputs, logs,
partial projections, failures and all prior matched-cohort evidence remain
untouched.

The baseline reviewer also identified missing complete-batch leading-axis
validation: NumPy could evaluate only a shortened temperature prefix. The
source now checks the exact homogeneous state/layout/certificate frame and
requires every numeric cohort/proposal/control leaf to share the complete
nonempty world axis before any per-world physics or vmap. Temperature and step
are exactly one scalar per prepared world. Ten prepared tests cover short/long
T, step and control arrays, single control/state leaves, truncated layouts and
certificates, and empty cohorts in NumPy and JAX shape tracing. A tripwire
forbids evaluating a prefix world. These new refusals are source-prepared and
**unrun**; the earlier matched-world numerical evidence remains scoped to its
frozen versions.

Memory reduction is a proposal pending coordination. First isolate shape,
projection and full-RHS compiler stages in fresh bounded processes. Telemetry
at durable stage boundaries suggests roughly 275 MiB after tracing, 300 MiB
after projection, and 312 MiB at full compilation start, so cache isolation
alone is not established as sufficient. Next consider compiling a compact
complete derivative/physical-field result, retaining raw proposals, original
arrays and diagnostic projections in separate buffers and composing unchanged
admission predicates without a giant nested duplicate result tree. If needed,
compile one unbatched physical world and map it across the cohort rather than
vectorizing the nonlinear solve graph. All 56 laws, all five families, every
physical derivative/field and reason predicate, exact owner maps, invalid raw
proposals, reorder/partition tests and existing tolerances must remain. No
increased guard, dropped law, relaxed check or automatic retry is authorized.
