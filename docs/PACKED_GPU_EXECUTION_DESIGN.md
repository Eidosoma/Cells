# Packed GPU execution (proposed design point, 15 November 2026)

**Status: proposed, no code.** The implementation lands in the execution layer.
`compile_window`'s key, which includes the structure, belongs to the core owner (D176).

**Why.** The user asked: "Can we pack together many tests on the GPU? we want to be able to do that
also in real runs", then "get active SM up to 80-90%". This note covers:
- a planner that packs worlds into vmapped batches;
- the batching rules;
- the telemetry and the acceptance.

The same planner serves the D172 GPU gate and production ensembles.

## Where we are on the L4 (records)

All rows are `resolved_pump_tissue@3`, the 825-node tissue, the vector-window path.
`device-checks-v3-20261109-01`, `study-01-gpu` and `study-02-gpu`, `results/summary.json`.

| Worlds per batch | ms per batch step | GPU busy | SM active (DCGM 1002) | SM occupancy (1003) |
| --- | --- | --- | --- | --- |
| 1 | 12.5 | 73.6% | 24.1% | 4.7% |
| 64 | 169 | 96.0% | 76.6% | 39.7% |
| 128 | 300 | 97.3% | **89.1%** | 47.7% |
| 256 | 585 | 98.1% | **92.8%** | 51.0% |

- **The target is already met at 128 or more worlds of one structure.** 80–90% SM active needs
  ≥ 128 worlds of the 825-node tissue.
- **The hold, at six worlds, sits far below it.** It is unmeasured; it would lie between the
  1-world and 64-world rows.
- **The guarded `lax.map` path** reached GPU busy 78–84% with SM activity below 1% (JUPITER
  runbook).
- **What limits small batches** (the L4 kernel profile of 14 November): batch size and kernel
  granularity.
  - At six worlds the step is about 60% cuBLAS batched triangular solves on single vectors. These
    are latency-bound, with few worlds per kernel.
  - Host synchronisation and launch overhead are ruled out (dispatch test: at most 1.37× from all
    loop control).
  - Compilation is a separate per-structure cost: 70–120 s per 825-node executable on the L4.

## The planner

1. **Structure key.** Model ID, law set (declared channel and pump laws, operators), padded
   shapes (cell, node, membrane, channel and species capacities), dtypes, and the plan. The plan
   covers the integrator and step, field solver ID, window length and observation schedule kind.
   - Worlds with equal keys share one executable.
   - The key is `compile_window`'s, owned by the core.
2. **Buckets.** Shapes are padded up to declared capacity buckets, so near sizes share a key. The
   padding cost is accepted only where it is below the batching gain.
   - Padding outputs follow check K1. Inactive slots hold padding, and the comparator exempts
     exactly those columns.
3. **Groups.** Each key forms one group, run as one vmapped batch through the vector-window path.
   Steps, device row checks and per-world refusal flags stay on the device. A refused world is
   masked and reported at the window's end, and the others continue.
   - Different keys run as sequential groups in **one GPU process**: each executable is compiled
     once and cached, and the GPU lock stays one process.
4. **Batch size from memory.** B = ⌊f × free device memory / per-world bytes⌋.
   - Per-world bytes come from P6's per-species and per-node costs, measured once per bucket.
   - Today's figure is about 14 GB at 256 worlds of 825 nodes with a preallocated allocator.
   - B is capped by the group's size. A group too small to reach the SM target is reported, not
     padded with fake worlds, unless the run declares replicate worlds.
5. **Window length.** W steps such that host work per window (observation transfer, summaries,
   snapshots) is at most 5% of the window's device time. No step makes a host round trip; the
   dispatch test found loop control costs at most 1.37×.

## Telemetry (GPU_ENSEMBLES.md's definitions)

For each group and over the warmed interval, report:
- SM active (DCGM 1002), SM occupancy (1003) and GPU busy (`nvidia-smi`);
- worlds and world-steps per GPU-hour;
- compilation seconds, peak device memory and execution seconds, separately.

Coverage rules are as defined there. Missing counters are unavailable, never zero. The headline is
the time-weighted SM activity over the warmed interval of a representative packed ensemble.

**Target.** 80–90% SM active, beside the registered 70% busy target. A group whose structure
cannot reach it (too few worlds, or kernels too small) is listed with its limiting factor.

## Acceptance: packed against scalar, once on the GPU

Packing changes the compiled program: batching, padding and grouping. Every result of record from
packed runs therefore needs the mode qualified once.
- **Packed against scalar, per world (G2-Q6 at scale).** Each world in a packed group against the
  same world run alone in the same process: every state field, observation, diagnostic and refusal.
  - **Bitwise** if today's Q7 test shows the deterministic flag gives bitwise L4 repeats; the
    packed and scalar runs then both run under it.
  - **Otherwise within the three-repeat run-to-run spread** (D168's fallback shape). At 825 nodes
    the L4 already scatters at 1.6e-11 relative, above Q6's 1e-12, so a bitwise or 1e-12 rule
    cannot hold there without the flag.
- **Refusals and stop rules:** identical per world.
- **The 13 L4 variants were registered on single-world runs.** A batched re-measurement is a new
  mode: its backend and run-to-run terms are measured in packed mode, and the verdicts are judged
  as registered.

## The packed D172 GPU gate

The D172 GPU checks run as packed groups:
- executable reuse for parameter-only changes;
- no kernel from an undeclared law;
- steps, checks and refusals inside device windows;
- performance up to about 150 species.

Each check's worlds form one or a few structure groups, so the gate fits one or two gaps.

**Pricing beside the serial options.**
- **Only the forward runs pack.** Their judges' host analyses do not: W2's stationary branches,
  G2's Q2 (R-ops), Q5 (dt sweep) and Q6 (restarts).
- **Serial re-measure of all 13:** about 8.4–8.8 h.
- **Packed, after the one-time qualification (about 1 h):** an estimated 4–5 h. The gain is
  limited by per-group compilation (about 1–2 min per structure, about 30 structures across the
  13 protocols) and by those host analyses. It is an estimate, to be measured in the qualification
  gap.
