# GPU execution and allocation efficiency

Execution scope reviewed: **2026-10-11**. Selected model families have CPU/L4
qualification; current results and active jobs live in [Progress](../PROGRESS.md).
Jupiter execution and remote scaling remain to be qualified. Feature development
and scientifically adequate CPU checks take priority; new GPU rounds are deferred
while compatible feature combinations and independent-world batches are prepared.

The deployment target is now **up to 16 GH200 GPUs on JUPITER**, across at most
four nodes. The [site configuration](https://apps.fz-juelich.de/jsc/hps/jupiter/configuration.html)
lists four GH200 superchips per node, each with 96 GB GPU memory and a 72-core
Arm CPU. These are separate device memories; a 16-GPU allocation is not a
single shared GPU address space. Site details were checked on 22 September 2026.

`cells ensemble plan DEFINITION --jupiter-nodes 4` produces an **offline**
16-GPU layout with global task/world identities, rank-to-node/device mappings,
per-node load estimates, and node/GPU-hour estimates including idle allocation
and the final tail. Nodes 1–4 are supported; definitions must contain enough
batches to use all devices. This does not enable remote execution: the existing
runner still rejects multi-node allocations until distributed ownership,
failure/resume and telemetry have been qualified on the cluster.

New mechanisms must retain pure array laws, explicit cell/species/interface
ownership, complete checkpoint state, and bounded recording. Independent worlds
can move between workers without changing their IDs or seeds. One interacting
tissue spread across GPUs additionally needs partitioned state, once-owned
boundary transfers, halo exchange at each required integration stage, and a
distributed field solver where applicable. It must reproduce the single-device
conservation and accuracy checks; ensemble scheduling alone cannot provide this.

Qualification proceeds on the L4, then one JUPITER node, then 2–4 nodes. Measure
every allocated GPU, compilation/I/O and tail costs, preserve the registered
scientific arm counts, and rebalance using measured costs when optimization
resumes. The earlier 70% utilization target remains advisory; it is not a
numerical acceptance criterion.

`finite_extracellular@2`, `finite_extracellular@3` and `spatial_extracellular@2`
accept `execution.backend: "gpu"` with JIT and float64. Normal runs, windows,
guarded independent-world batches and complete
checkpoints use the selected device. GPU requests fail when CUDA is unavailable.
Other ionic schemas retain their previous device contracts. CUDA environments
can also run explicit CPU comparisons without disabling subsequent GPU use.

GPU snapshots record CUDA packages, GPU kind and CUDA platform version. Saved
continuation is checked on the same runtime/device kind. Moving from L4/x86 to
GH200/Arm needs new numerical qualification. The physical RK4/domain checks
are unchanged. Guarded ionic batches still use `lax.map`; functional GPU support
does not establish high ionic throughput. Later [tissue and resolved-surface
families](TISSUE_RETURN_CURRENT.md) also have explicit CPU/GPU paths. Their bounded
field solves do not establish large-mesh or distributed-field performance.

For the next feature batches, group matching model/state layouts and accepted
numerical clocks, while keeping case identities, controls and evidence separate.
Include coupled transport/water/energy cases and the appropriate disabled-route
controls in the later qualification. A richer model exercises more mechanisms;
it does not by itself demonstrate higher SM activity. The production guarded
ionic path still maps worlds sequentially with `lax.map`. Concurrent world
execution needs the same invalid-trial, finished-world, conservation and restart
checks, including the existing experimental parallel paths below.

Measure compilation and warmed execution separately, and retain both GPU-busy
and SM-active with coverage. Use measured per-batch costs to balance a four-GPU
node before extending to sixteen GPUs. Runtime packing must preserve simulation
duration, refinement, reference comparisons and scientific arm counts; numerical
controls are not additional independent biological cases.

## Independent model ensembles

`python -m cells.ensemble` and `cells ensemble` provide `plan`, `run`, `status`,
`resume` and `balance`. A node owns a shared queue of registered batches. Each
GPU has one or two persistent processes; two can supply work while another
process performs host checks or writes checkpoints. Kernels are reused within
each process. The benefit is a performance hypothesis to measure per workload.

Arms fix their physical definitions and total sample counts. Each batch gets
a disjoint range of stable world IDs and the registered seed. Batch boundaries,
worker count and task order do not change a world's random stream. Controls and
sample counts within a registered campaign are never changed to fill a device. Full event checkpoints remain
available for completed and interrupted batches.

Offline ionic planning fully validates each arm and exact batch size once per
plan. Repeated tasks retain deep copies of that complete definition, with every
world-ID range checked separately; a smaller final batch receives its own
validation and resource estimate. Each new planning call and every executing
worker still validates its input. This reduces repeated preparation work without
changing scientific settings, identities or numerical checks.

The output estimate includes complete checkpoints and serialized source history,
including carried INIT state for phase-handoff models. A rejected plan reports
both required and declared bytes. `max_output_bytes` is a disk allowance;
working-memory and process-memory limits are separate.

`assembly_ensemble@1` retains the original
fixed-bath `capsid_graph@1` rules; `finite_bond_ensemble@1` requires the finite-pool
`finite_bond_assembly@1` model in every arm. The latter uses first passage to
20 occupied sites **and all 30 bonds** for completion/survival summaries; this
does not imply the cage remains assembled. Its reports also retain current
cage counts, full-cage dwell, reaction counts and exact finite-material totals.
The same dynamic queue and complete pause/resume contracts also serve the
integrated models. `assembly_cell_ensemble@1` accepts `assembly_regulated_cell@1`
arms; the scheduler owns `pool.seed`, `pool.worlds` and `pool.world_id_start`.
It uses the existing event-split engine and complete assembly/ionic checkpoints,
including pending events. Per-arm reports retain assembly material and cage
statistics alongside voltage, channel transfer and availability exposure.

`assembly_cluster_ensemble@1` accepts `assembly_regulated_cluster@1`. A world
contains the complete interacting spatial cluster and every cell-owned assembly
pool. The scheduler owns each pool's world count, starting world ID and seed;
arm definitions omit those three fields. Each explicit cell `stream_id` derives
its seed from the ensemble seed modulo 2^32. Task partitioning and placement
retain those identities, including in offline plans for up to 16 GPUs. Each
cell's material and cage statistics are reported separately over the registered
world count. There is no implicit cluster cage-completion probability. Per-cell
voltages, channel transfers, availability exposures and ionic accounting remain
available alongside those statistics. GPU launches require an explicit GPU
backend in the nested ionic definition. This adapter uses the existing shared
queue and complete checkpoint lifecycle; throughput and multi-GPU scaling still
need measurements for this model.

`validation/ensemble/cluster_matrix.py --parent COMPLETED_CLUSTER_QUALIFICATION
--output FRESH_WORKSPACE_DIRECTORY` prepares its L4 cost profile for the ordinary
ensemble launcher. It authenticates completed CPU/L4 evidence and requires the
same production code. Dynamic assembly, a fixed ring and a fixed open control
each use 128 worlds at batch sizes 32 and 64: 768 worlds across six profiling
arms and 18 tasks. Two persistent workers share the L4. Rates, structures,
the 50-microsecond timestep, 20-ms horizon, observations, 32-tick windows and
scientific checks remain unchanged. Only scheduler-owned population fields and
explicit GPU routing differ from the saved definitions. Dynamic arms use
distinct random world IDs; the fixed controls are deterministic replicas.
Timing samples across batch sizes are unpaired and include compilation, host
work and checkpoint writes. The preparation retains a 4-GiB disk reserve plus
256 MiB for caches and does not launch a run or establish multi-GPU efficiency.

The same preparation command with `--family calcium` accepts a completed
spatial-calcium/assembly CPU/L4 qualification. It uses that run's frozen
`assembly_regulated_calcium_cluster.json` and authenticated GPU evidence, and
requires identical production code. The dynamic model uses 64 worlds at each
batch size **8, 16 and 32**: **192 worlds in 14 tasks**, with two persistent
workers and a 30-minute cap. Its **12.5-microsecond timestep, 20-ms horizon,
16-tick windows**, observations, per-cell random streams and numerical checks
are preserved. Arms have equal world counts and disjoint world IDs; their
timings measure local batch costs rather than paired speedup. The ordinary
ensemble runner retains full checkpoints, utilization telemetry, phase timings
and the cost profile for subsequent scheduling.

`--family plasma` and `--family gated` select qualified `spatial_calcium@2`
and `spatial_calcium@3` assembly examples respectively. Each uses **64 worlds
at batch sizes 16 and 32**, for **128 worlds / six tasks**, with the same
timestep, horizon, windows and checks as its qualified parent. The gated
family binds the saved CaV1.2 assembly/reference/replay evidence and retains
all calcium-channel states and ledgers. Preparation reserves **8 GiB per
plasma worker / 10 GiB per gated worker**, plus **4 GiB** of host memory;
these are conservative prelaunch allowances, not enforced RSS limits.

`--family ip3` selects the qualified `spatial_calcium@4` assembly example and
binds its saved IP3 assembly/reference/replay and CPU/L4 comparison evidence.
It uses the same **128 worlds / six tasks**, at batch sizes **16 and 32**,
with all ligand chemistry, timestep, windows and checks preserved. The IP3
preparation reserves **16 GiB per worker plus 4 GiB**, covering the completed
qualification's 14.84-GiB peak child RSS conservatively. If the host cannot fit
two workers, `--workers-per-gpu 1` uses one persistent worker with both CPU
cores and a one-hour cap. The default remains two workers with one core each
and a 30-minute cap. This choice changes execution resources, not scientific
worlds or numerical accuracy. A single-worker profile measures utilization
and batch costs; concurrent-worker balance requires a separate profile.

`validation/ensemble/profile_cluster.py launch --preparation PREPARED_IP3_PROFILE
--parent COMPLETED_IP3_PROFILE --output FRESH_WORKSPACE_DIRECTORY` replays the
same single-worker task plan with diagnostic observers. It freezes production
source and the observer driver, then uses the ordinary ensemble controller,
worker, conservation checks and complete checkpoints. One-second process-tree
samples record CPU time, resident memory and available host memory; worker
receipts also retain lifetime peak RSS. A JAX/CUPTI trace captures windows 3–4
of the first task at each batch size, after compilation and two completed
windows. The final check requires every saved state field to match the parent
bit for bit. Logs, traces and result/failure artifacts stay under the output
directory; no follow-up run is scheduled. The prelaunch allowance adds 2 GiB
for tracing to the prepared worker allowance and 4-GiB reserve. Instrumentation
affects timing and memory, and its traces need interpretation before changing
concurrency; it is not an uninstrumented throughput comparison.

After that diagnostic completes, `cluster_matrix.py --memory-profile
COMPLETED_DIAGNOSTIC` can size workers from authenticated memory evidence for
the same production source and workload. It takes the larger of worker peak
RSS and sampled process-tree RSS, adds 25%, and rounds up to the next GiB.
The 4-GiB host reserve remains required. Without that explicit evidence, the
original conservative allowances still apply. This is a sizing estimate;
simultaneous compilation and resource use must still be measured.

`profile_cluster.py launch --mode throughput --preparation PREPARED_TWO_WORKER_PROFILE
--parent COMPLETED_UNTRACED_PROFILE --output FRESH_WORKSPACE_DIRECTORY` uses
two workers, one CPU core each and a 30-minute campaign cap. It keeps resource
samples and per-window counters, disables GPU tracing, starts with fresh caches,
and requires exact saved-state agreement with the same worlds from the prior
single-worker campaign. It records whole-allocation utilization, throughput,
worker/arm finish gaps and memory. A one-second memory guard requests the
ordinary controller's checkpoint pause if total process-tree RSS exceeds the
prepared workers' combined allowance, available memory falls below 4 GiB, or
resource sampling fails. This is a sampled cooperative guard, not an
instantaneous RSS limit. The controller retains its existing bounded pause and
failure handling. No automatic retry, follow-up experiment or cluster run follows.

Add `--dcgm-root /mnt/workspaces/Cells/tools/dcgm-4.7.0` to the throughput replay
to collect actual GPU hardware counters at one-second intervals. This optional
tool bundle contains extracted, checksum-verified NVIDIA DCGM 4.7.0 runtime
packages and an `installation.json` receipt; it does not install a system service.
The sampler uses the selected GPU's UUID, checks its supported counter groups,
and refuses a set requiring multiplexing. Only this isolated monitoring process
uses `sudo -n` for NVIDIA profiling privileges; simulation workers run normally.
The driver freezes the sampler and binds the runtime hashes. The sampler must
return valid counters before the campaign starts, exits when its controller
closes input, and has a separate timeout beyond the campaign's wall limit.

`gpu-counters.jsonl` retains device timestamps, raw statuses, SM activity
(field 1002), SM occupancy (1003), graphics-engine activity (1001), and DRAM
activity (1005). `gpu-counter-summary.json` reports time-weighted whole-campaign
and post-warm-up means, with coverage for each field. Missing/invalid values
are not zeroes; repeated timestamps and gaps over 1.5 seconds do not extend
coverage. Completion requires at least 98% coverage in both intervals, as well
as the ordinary numerical checks and exact checkpoint comparison. Failed
measurement evidence is retained. Counter intervals crossing a reporting
boundary are clipped assuming a constant rate within that one-second interval.
SM activity measures time with an active warp, averaged across SMs; occupancy
measures resident warps relative to capacity. Both include stalled warps, so
neither is arithmetic efficiency. These are separate from `nvidia-smi` GPU busy
time and the kernel trace's theoretical occupancy. See
[NVIDIA's counter definitions](https://docs.nvidia.com/datacenter/dcgm/latest/learn/modules/profiling.html).
Timing includes DCGM overhead; compare it with the uninstrumented baseline.

`PYTHONPATH=src:. python -m validation.ensemble.parallel_cluster launch
--parent COMPLETED_IP3_CAMPAIGN --output FRESH_WORKSPACE_DIRECTORY` screens
experimental world batching against the unchanged scalar implementation.
It freezes two candidates: fixed 32-world tiles, and the same tiles with scalar
extracellular-field evaluation. Padding repeats complete independent worlds
and discards their outputs. Three registered worlds undergo full-state scalar
comparison, disk restart with changed window sizes, partition replay, ordinary
stage/accounting checks, and CPU/L4 agreement. Same-device comparisons remain
bitwise exact; CPU/L4 tolerances are unchanged. CPU and L4 phases run sequentially
with 45-minute caps, durable evidence and explicit failure reports. A completed
screen can reject both candidates. Passing makes a candidate eligible for larger
qualification; it does not change production defaults, measure throughput or
SM activity, or schedule a follow-up run.

Use `--variants parallel_scalar_linear` to screen scalar batching of only the
field's dense linear solve; `parallel_scalar_linear_sums` also keeps the field
sums scalar. Both reuse the original field equations and NumPy observations.
`--cpu-tile-width 4 --gpu-tile-width 32 --run-wall-seconds 1200` reduces CPU
padding and allows compilation plus execution more time. The registration binds
both fixed tile widths and the changed wall budget; seeds, physical inputs,
integration grids and numerical tolerances remain the same. Each phase still has
a 45-minute cap. Launch requires a 14-GiB worker allowance plus 4-GiB host reserve,
covering the preceding screen's observed memory with headroom; this preflight is
not a live RSS limit. Missing CPU or GPU endpoints remain explicitly unevaluated
and cannot pass qualification.

Add `--rounding-parent COMPLETED_CANDIDATE_SCREEN` with the same candidate,
tile widths and run budget to diagnose its exact-reference mismatch. This mode
authenticates the prior screen and unchanged candidate, then records the complete
state after every physical tick on CPU and L4. It saves the first differing tick,
the first difference in each field, and both states immediately before and after
the first difference. Both traced endpoints must reproduce their saved screen
endpoints bit for bit; otherwise the trace has not reproduced the original case.
Same-input isolated field and full-rate-equation probes at those reference states
provide further diagnostic evidence, with their limited compilation context
explicitly distinguished from the integrator. The existing detached runner,
45-minute phase caps, resource monitoring and durable failures remain in use.
This mode makes no acceptance or performance claim and schedules no follow-up.

Use `--step-parent COMPLETED_ROUNDING_TRACE --variants parallel_scalar_linear`
with the same widths and run budget to compare selected operations at saved
rounding witnesses. The reference and unchanged candidate must reproduce their
own saved steps first. Experiments then use identical reference inputs at the
union of both devices' first differing ticks per field, plus the final step.
The existing solve-only, solve-plus-sums and whole-field strategies are compared
with scalar batching of the original logarithmic mean plus dense solve. No field
equations are copied or changed. Each variant saves complete before/after states,
exact comparisons, ordinary accounting and its lowered/optimized compiler text.
The usual detached runner, phase caps and durable failures apply. Agreement at
these selected steps does not qualify full trajectories or establish an exact
compiler cause, throughput or SM utilization; follow-up runs remain separate.

Use `--gpu-screen-parent COMPLETED_SAVED_STEP_SCREEN
--variants parallel_scalar_linear_sums` with the registered widths and run budget
to screen the GPU candidate while retaining the ordinary scalar CPU path.
Launch requires authenticated, passing GPU witnesses and unchanged candidate code.
The CPU reference is rerun and must reproduce its saved endpoint. The complete
GPU run uses one-tick observation windows and compares every state at all 1600
physical ticks with the authenticated scalar GPU trace. Transient differences
remain failures even if the final state agrees. The half run, seven-tick-window
restart and world partitions also compare every output window with that trace,
alongside the ordinary complete-checkpoint and endpoint replay checks. CPU/GPU
agreement retains the existing tolerances. Partial traces and the first differing
states are preserved on failure. Acceptance is explicitly limited to this GPU
screen; CPU batching, production defaults and performance qualification remain
separate. The detached runner schedules no follow-up.

Use `--larger-screen-parent COMPLETED_GPU_SCREEN
--variants parallel_scalar_linear_sums --cpu-tile-width 4 --gpu-tile-width 32
--run-wall-seconds 1200` for the next bounded numerical qualification. This
selects 65 worlds from the same authenticated campaign, exercising two complete
32-world tiles and a padded partial tile. Reference checkpoints are assembled
in world-ID order; missing, duplicated or physically different worlds are refused.
A fresh scalar GPU run saves all 1601 states and must reproduce those qualified
endpoints exactly. The candidate is compared against that entire trace, including
all output windows of its half run, seven-tick-window restart and partitions of
32 and 33 worlds. The ordinary scalar CPU endpoint reproduces the preceding
three-world subset and supplies the CPU/GPU comparison for all 65 worlds.
The candidate code, physics, streams and tolerances remain bound to the preceding
screen. The same 45-minute phase caps, resource preflight and detached evidence
apply. Passing permits a separate throughput/SM measurement; it does not launch
one or change production defaults.

Use `--energy-step-parent COMPLETED_LARGER_SCREEN` with the same candidate,
widths and run budget to diagnose a rejected larger trajectory whose only
differences are in membrane dissipated energy and whose endpoint checks pass.
The existing saved-step runner retains all 65 worlds and selects each affected
world's first divergence, the maximum-ULP case, final recovery and final tick.
Only the GPU executes; the completed CPU reference remains authenticated evidence.
Scalar and unchanged batched paths must reproduce their own saved states before
the experimental results can be interpreted. The experiments retain the original
equations while protecting the membrane energy reduction, full leak/pump energy
rate, combined membrane energy rate, or complete checked RK4 operation. Every
experiment starts from the same complete scalar reference input and saves all
state comparisons and compiler text. These selected steps diagnose rounding;
any proposed fix still requires full-trajectory qualification. The detached
runner retains its 45-minute cap and schedules no follow-up.

Use `--energy-screen-parent COMPLETED_ENERGY_DIAGNOSTIC
--variants parallel_scalar_membrane_sum` with the same widths and budget for
complete 65-world qualification of the narrowest passing protection. The runner
requires exact saved-step agreement and authenticates both the original batching
code and the energy-wrapper source against that diagnostic. It reuses the full
authenticated scalar GPU trace, checks its endpoint against the qualified
campaign checkpoints, and reruns the ordinary scalar CPU reference for all
65 worlds. The candidate must match every physical tick, every replay output
window, the complete checkpoint roundtrip, seven-tick-window restart and world
partitions of 32 and 33. Checkpoint provenance identifies the additional wrapper.
CPU/GPU tolerances and all physical/domain checks remain unchanged. The same
detached runner and phase caps apply; throughput and SM measurement follow
review of the completed result.

`ionic_ensemble@1` accepts an explicit `ionic_worlds@1` wrapper containing
`simulation` (an ordinary `finite_extracellular@2`, `@3` or `spatial_extracellular@2` definition),
`window_steps`, and optional working/output/wall limits. The scheduler owns
the wrapper's seed/count/IDs. Execution uses ordinary guarded batch windows;
checkpoints wrap the existing complete scalar cohort snapshots. The cohort's
positive IDs equal the scheduler's zero-based IDs plus one. Identical ionic
replicas are deterministic throughput work; they do not add stochastic samples.
Their reports contain ionic observables and integrated world steps, with no
assembly completion statistics. Both integrated kinds require an explicit GPU
backend in the nested ionic definition when launched on the GPU scheduler.

These adapters preserve the existing equations, timesteps, stage refusal and
conservation checks. The assembly/cell runner additionally separates preparation,
compilation, execution, transfers, callbacks and final validation/summary costs.
[Integrated profile definitions](../validation/ensemble/integrated_matrix.py)
compare two batch sizes for each family. Numerical qualification and measured
throughput status live in [Progress](../PROGRESS.md); scheduler support alone
does not establish four-GPU efficiency. The qualification runner also accepts
`--ensemble-profile --profile-scale throughput --baseline COMPLETED_PILOT`.
This registers a larger capacity study from authenticated pilot definitions:
32,768 assembly–cell worlds in batches of 2,048, and 1,024 ionic worlds in
batches of 64. Assembly–cell uses one 200-tick window, avoiding a second compiled
tail shape. Rates, the integration timestep and the 20-ms horizon come from the
baseline. The larger stochastic sample is a separate performance study; speedup
or biological comparisons require matched workloads.

`validation/ensemble/spatial_matrix.py --parent COMPLETED_SPATIAL_PANEL --output
FRESH_WORKSPACE_DIRECTORY` prepares a separate spatial cost profile for the
ordinary ensemble launcher. It authenticates the qualified parent and requires
unchanged production code. Baseline and pump-release cases each use 128
deterministic replicas at batch sizes 16 and 64, for 512 worlds across four
profiling arms. The finest qualified timestep, physical parameters, controls,
observations and horizon are copied exactly; four equal 200-step windows keep
both batch sizes within the existing memory allowance. Two persistent workers
share the L4 and retain every ordinary
domain, accounting and complete-checkpoint check. Per-arm costs include host
work and checkpoint writes; whole-job telemetry includes compilation and the
final tail. Preparation does not launch a job, change scientific counts to fill
GPUs, or establish multi-GPU scaling.

Ionic cohort checkpoint publication captures source/runtime identity once and
rechecks it before writing the enclosing manifest. Each world still receives a
complete ordinary scalar checkpoint with its own definition, state/layout arrays
and byte checksums. Identity is freshly collected for every publication; a
source/runtime change during writing prevents publication of the cohort manifest.

The planner prioritizes the arm with the most estimated remaining work. Free
workers take the next batch, including work belonging to other arms. Measured
costs can shorten batches from slower arms and reduce the final tail.
`cost-profile.json` records per-arm wall time per world, including compilation,
host checks and I/O. Costs at another batch size or on another GPU remain
planning estimates and need another measurement.

The first concentration experiment fixes **27 arms**: three initial structures
× free-trimer concentrations of **5.6, 9 and 17 nM** × detachment rates of
**5, 10 and 20 /s**. Association is `1e7 M^-1 s^-1`; the observation horizon is
**300 s**. Every arm has **32,768 worlds**, totaling **884,736 independent
worlds**. Initial batches contain 32,768 worlds, with two workers per GPU.

This is a model experiment and throughput study. Prescribed geometry, protected
cycles, the anchored root and maintained bath remain assumptions. Ring and open
chain match five initial trimers; the single-trimer control has different initial
material. Reports include Wilson 95% intervals for completion probability,
completion survival curves, size/dwell distributions and restricted mean wait
through the fixed horizon. They do not fit experimental data or test renewable heredity.

Example local launch; choose new output names:

```bash
PYTHONPATH=src /mnt/workspaces/Cells/venv-gpu/bin/python -B \
  validation/assembly/concentration_matrix.py \
  --output /mnt/workspaces/Cells/assembly-matrix.json
PYTHONPATH=src /mnt/workspaces/Cells/venv-gpu/bin/python -B -m cells.ensemble \
  plan /mnt/workspaces/Cells/assembly-matrix.json --allocated-gpus 4
PYTHONPATH=src /mnt/workspaces/Cells/venv-gpu/bin/python -B -m cells.ensemble \
  run /mnt/workspaces/Cells/assembly-matrix.json --devices 0 --allocated-gpus 1 \
  --output /mnt/workspaces/Cells/assembly-matrix-run --detach
```

The detached launcher freezes source and records logs, inputs, world ranges,
device identities, budgets and result/failure artifacts. `status RUN` reads saved
status once. Completion launches no automatic retry, campaign or scheduler job.

## Utilization and the node budget

Current reporting records **GPU-busy time and measured SM-active percentage**,
per-device coverage, throughput, allocated GPU/node time and arm finish gaps.
Report whole-run and warmed measurements where a meaningful warmed interval
exists. A mixed correctness suite with repeated compilation may have no such
interval; say so. Missing hardware counters are unavailable, not measured zeros.
Check telemetry support before each runner's next GPU campaign; do not infer
coverage for an older run that did not collect the counters.

The original registered target was **70% mean GPU busy time on every allocated GPU** across
the whole allocation/runner interval. It is an advisory performance target;
mixed CPU/GPU work may justify a different registered target after measurement.
Any positive target up to 100% is supported. A separate measure starts after all
workers warm up. Each measure includes its idle gaps and final tail. A numerical
pass with poor utilization retains valid numerical evidence and reports the
missed efficiency target. `ready_for_node_pilot` still means numerical completion
and passing that registered utilization target; it does not submit or prevent
a manually chosen pilot. The initial 70% target remains in the matched matrix.

The original `gpu-utilization.jsonl` target check samples allocated GPU UUIDs
about once per second. Its report time-weights readings, scores missing intervals
as zero for that legacy target, and requires
at least 30 seconds with 90% telemetry coverage. A long monitor gap cannot reuse
an old high reading; the score must not be presented as a measured counter value
over those missing intervals. NVIDIA GPU busy percent, SM-active time and SM
occupancy are different measurements;
useful worlds/events per wall time also matter. Fresh completed campaigns report
worlds and committed events per allocated GPU-hour. Resumed campaigns leave
those ratios unset: their inherited work needs cumulative allocation accounting
before a fair throughput comparison. Compare identical scientific workloads,
including precision, checks, sample counts, observation horizon and checkpoints.
A lower allocation cost is useful even if GPU busy time remains below 70%.

Task reports separate initialization, compilation, kernel execution, device-to-host
transfers, callbacks, final state validation, summaries, checkpoint writing and
ensemble observations. Synchronous kernel times across overlapping workers are
process measurements; their sum is not measured GPU busy time. Graph checks reuse
bounded, immutable oracle answers and still check every world's saved target.
Checkpoints use lossless deflate level one with unchanged full-state arrays,
hash checks and uncompressed-size bounds. The complete payload is flushed before
its manifest is published. Current measurements and source-linked evidence live
in [Progress](../PROGRESS.md).

Phase-by-phase host timings and cached pending-event validation currently apply
to the original assembly family. The finite-pool runner reports compilation,
synchronized execution and total time; its host validation remains a candidate
for profiling. Do not transfer a measured speedup between the two kinetic models.

GPU-hours are **physical allocated GPUs × elapsed allocation hours**. Two
processes on one GPU count as one GPU. Omitting GPUs declared by
`SLURM_GPUS_ON_NODE`, or using this launcher for multiple nodes, is refused.
On Slurm, accounting starts at `SLURM_JOB_START_TIME`, including unmeasured
startup as zero utilization, and stopping respects `SLURM_JOB_END_TIME`.
These fields are documented by [Slurm](https://slurm.schedmd.com/sbatch.html).
The local interval starts at launcher entry. Hours end at result aggregation;
reconcile the final charge with the scheduler's completed allocation receipt.

After inspecting a completed study, generate a fresh balanced definition:

```bash
python -m cells.ensemble balance ORIGINAL.json --profile RUN/cost-profile.json \
  --output /mnt/workspaces/Cells/balanced-matrix.json \
  --target-task-seconds 30 --allocated-gpus 4
```

This preserves scientific counts, caps batches at their previous size bounds,
and records estimated tail imbalance and the timing source. It does not submit
work. Use it for a fresh campaign; interrupted campaigns keep their existing batches.

## Interruption and JUPITER preparation

`SIGUSR1` or `SIGTERM` stops assignment and saves running batches at the next
event-chunk boundary, including pending events and material ledgers. Time is
reserved before the wall limit. A compiler/kernel that misses the grace period
is killed and recorded as failure without a false complete checkpoint.
`cells ensemble resume OLD --output NEW --allocated-gpus N --devices all`
continues a saved pause using frozen source/runtime. Completed batches are linked
by hashes; unfinished batches retain their original world IDs. Scientific failures
are not automatically retried.

`CELLS_OUTPUT_ROOT` changes `/mnt/workspaces` to an explicit site scratch root;
caches follow it. The [one-node Slurm template](../validation/ensemble/jupiter.sbatch)
requires qualified Arm CUDA/JAX Python and explicit source/scratch paths. Supply
the account and scratch stdout/stderr paths to `sbatch`. Inside an allocation,
the runner stays in the foreground for scheduler signals and exit status.

Deployment, NUMA placement, CPU sidecar packing and measured four-GPU efficiency
remain to be checked on the actual node. The local longer reference study runs
on separate reserved CPU cores. Existing fleet tooling can pack registered CPU
reference/analysis tasks beside GPU work; this template does not invent or
automatically submit additional CPU experiments.
