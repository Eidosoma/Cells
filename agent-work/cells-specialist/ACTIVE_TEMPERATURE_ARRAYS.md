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

The original CPU JAX attempt was staged per family: shape tracing, compiled
numeric projection, then lowering/compiling/executing the full two-world RHS/field
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
forbids evaluating a prefix world. The focused axis run
`physiology-active-temperature-arrays-axis-20261030-01` passed ten checks and
120 independently replayed malformed declarations. The separate positive run
`physiology-active-temperature-arrays-matched-20261030-01` passed five family
cohorts and 15 independent complete derivative/field records. Their completion
receipts verify frozen sources, runtime files, imports and measured limits.
These captures precede the compact-stage candidate below; the qualification
plan links each exact frozen version.

Chief then authorized compact-output source development, with no compiled JAX
retry. Telemetry at durable stage boundaries suggests roughly 275 MiB after
tracing, 300 MiB after projection, and 312 MiB at full compilation start, so
fresh-process cache isolation alone is not established as sufficient.

The new candidate exposes separate pure world stages. `prepare_numeric_world`
keeps raw projections, safe arithmetic inputs and all six input predicates.
`compact_physics_world` runs the original complete readout kernel and returns
one complete derivative, the whole physical field tree, original model validity
and actual per-owner gross hydrolysis/synthesis. Nested parent readout copies
are not compiler outputs. `check_physics_world` retains the seven physical
predicates, including original domain checks, field convergence, complete finite
rates, energy, dissipation and actual passive/fuel turnover. Assembly attaches
the unchanged thirteen reason bits and exact raw proposal without another
derivative leaf copy.

`WorldStages` can carry three individually compiled family-bound functions.
`evaluate_batch_staged` first checks the complete cohort protocol, then calls
each world separately and stacks every output. Neither the nonlinear field
solve nor its complete rate graph is vmapped in this path. Compiling the entire
composition would fuse/unroll it again, so the convenience world/batch wrappers
must not be jitted as one executable. Separate stage calls are an execution
boundary, not a changed physical law. Original `project`, `evaluate_world`,
`evaluate_batch` and their protocol/turnover helpers are AST-identical to the
verified matched capture; the monolithic path remains available for parity.

Twenty additional prepared tests cover exact shared output parity and all 32
independent fields, stage call boundaries, raw nonfinite proposals, actual gross
fuel flows, exact cohort reorder/partition, all seven physical refusal
predicates and separate JAX shape tracing. Both batch entrypoints must refuse
all malformed world axes before prefix projection/physics. The independent
reference's six input predicates are factored without changing their
expressions so raw nonfinite NPZ evidence can also replay under import denial.

This candidate is **source-prepared, statically checked and numerically unrun**.
No reduced compiled RSS or successful compiled RHS is claimed. The prepared
host runner selects 56 checks and 40 independent full-rate/field records in
seven bounded phases, with compiled JAX disabled. A future compiled runner must
freeze a distinct capture, isolate compiler stages in fresh bounded processes
and execute the separate complete unbatched physical stage before mapping all
worlds. Aggregate runs expected to reach ten minutes launch detached and are
not automatically polled. Chief's next instruction is required for either
qualification. All 56 laws, five families, complete physical outputs/predicates,
exact owners and existing tolerances remain required; the 1 GiB/8 GiB/480 s
limits are unchanged.
