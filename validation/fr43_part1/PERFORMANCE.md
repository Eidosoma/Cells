# FR-43 part 1: performance on the CPU (C1.4)

FR-43's case C1.4 asks for four figures:
- the compile time;
- the time per simulated second after compilation;
- the peak memory, at one declared accuracy;
- the device and the precision.

It asks for them at 16 rows (the control), 32, 256 and 1,024 rows. The design note measured these before part 1 landed
(`docs/FR43_SHARED_INVENTORIES_DESIGN.md` §1.2, §1.4, §1.8). D347's gap 2 found that they lived only there, and D365
asked for them on the CPU. These are the landed engine's figures.

`performance.json`, beside this note, holds:
- every repeat's figures, record, command and environment;
- the design's records, which are compared below.

**Engine models it runs:**
- `resolved_pump_composite@1` over `resolved_pump_tissue@3`, with `local_species_reactions@1`, whose links are
  `ideal_detailed_balance_mass_action@1`;
- the solver `imex_ars222_face_electromigration@1`;
- the field solver `capacitive_reduction_gauged_damped_newton@2`.

## How it ran

**The world** is FR-43's chain (`tests/species_cap_fixtures.chain_world`), the world of the species-cap tests and of
the design probe.
- One 1 pL cell on its held bath, with Na, K and Cl.
- A reversible chain of rows − 3 neutral species, whose links are fast (20 s⁻¹) and slow (0.2 s⁻¹) in turn. The
  values are synthetic.
- A step of 5 ms over 2 s (400 steps), observed every 0.25 s, through the runner (jit) with every host check on at
  every row.

**The declared accuracy** is the note's. The largest error against expm(K t) n₀, over every saved step and species, is
at most 2 × 10⁻⁵ of the largest initial amount. Every repeat:
- met it, at 1.63 × 10⁻⁵;
- saw the planted link (0.1% fast) at 9.3 to 13.7 times the accuracy;
- closed material to 2.1 × 10⁻¹⁸ fmol, and energy to 4.9 × 10⁻¹⁵ relative;
- booked heat equal to the free-energy drop within 1.9 × 10⁻¹³.

**The source** is revision `4f4c4812`, on branch `fr43-part1-gaps` from main `cfb08756`; its `src/` is `cfb08756`'s. It
ran from its frozen execution snapshot, `/mnt/workspaces/Cells/fr43-part1-gaps-20261124/snapshot-4f4c4812` (made with
`scripts/gates/freeze_snapshot.py`, scope full, clean).

**The command.** Each figure is one fresh process, run from the snapshot in the detached unit `cells-fr43-part1-perf`:

    flock /mnt/workspaces/Cells/locks/timed-cores-4-5.lock taskset -c 4 /mnt/workspaces/Cells/venv-cpu/bin/python -B scripts/profile_species_chain.py run --rows N --out OUT

- The lock was taken for each figure and released between figures.
- There were three repeats per size, in rounds of 16, 32, 256 and 1,024 rows
  (`/mnt/workspaces/Cells/fr43-part1-gaps-20261124/perf/out/queue.sh.ran`).

**The environment:**
- CPU 4 (Intel Xeon @ 2.20 GHz), one thread, device `cpu:0`, float64;
- JAX and jaxlib 0.11.1, NumPy 2.5.3, SciPy 1.18.1, Python 3.13.5, and OpenBLAS at one thread;
- JAX's compilation cache disabled, and `XLA_FLAGS` unset.

CPU 5 and the siblings 20 and 21 ran no timed work. Unpinned processes kept them 7% to 54% busy, and each record gives
the fractions.

**The timings** are the runner's (`RunResult.timings`):
- compile is `compile_or_cache_seconds`;
- execute is the compiled rollout, until its results are ready;
- the time per simulated second is execute over 2 s;
- the host checks are `analysis_seconds`.

**Peak memory** is the process's peak resident set (`ru_maxrss`), read right after the run and before the closed form.

## The figures

Each figure is the median of three repeats, with the range in parentheses.

| Rows (ions + chain) | Compile s | ms per step | s per simulated s | Peak RSS MiB | Host checks s | Build + parse s |
| --- | --- | --- | --- | --- | --- | --- |
| 16 (3 + 13), the control | 18.4 (18.4–19.1) | 0.23 (0.23–0.36) | 0.046 (0.046–0.072) | 833 (827–836) | 1.2 (0.9–1.2) | 1.7 |
| 32 (3 + 29) | 21.0 (20.9–21.4) | 0.48 (0.46–0.50) | 0.095 (0.092–0.100) | 866 (865–873) | 0.9 (0.9–1.1) | 1.9 |
| 256 (3 + 253) | 24.3 (23.0–24.8) | 16.5 (15.9–18.2) | 3.3 (3.2–3.6) | 939 (938–942) | 1.4 (1.4–2.2) | 2.2 |
| 1,024 (3 + 1,021) | 47.0 (44.1–47.1) | 455 (429–463) | 91 (86–93) | 1,746 (1,742–1,748) | 3.9 (3.5–4.4) | 5.4 |

- **The step's cost** grows about as the square of the rows above 32, from the dense [rows, route] layout (§1.6).
- **Compile time** grows slowly, since sums above 16 terms fold by a scan.

## Against the design note

The note ran this world from the design snapshot `92e18df4`, with the cap raised in its process, in two arms of the
species sum. The landed gate keeps the unrolled sum up to 16 terms and uses a scan above that. So 16 rows compare with
the note's unrolled arm, and the larger sizes with its scan arm (§1.4).

| Rows | Note's arm | Compile s, note / now | ms per step, note / now | Peak RSS MiB, note / now |
| --- | --- | --- | --- | --- |
| 16 | unrolled | 20.4 / 18.4 | 0.26 / 0.23 | 835 / 833 |
| 32 | scan | 20.2 / 21.0 | 0.47 / 0.48 | 867 / 866 |
| 256 | scan | 23.1 / 24.3 | 16.4 / 16.5 | 937 / 939 |
| 1,024 | scan | 42.2 / 47.0 | 431 / 455 | 1,738 / 1,746 |

**They agree:**
- The accuracy and the memory are the note's.
- **The step's cost follows the sibling thread's load.**
  - The least loaded repeats (CPU 20 at 7% to 9% busy) took 15.9 ms at 256 rows and 429 ms at 1,024, against the
    note's 16.4 and 431.
  - The most loaded (25% to 27% busy) took 18.2 and 463.
- **Compile at 1,024 rows** is 5% to 12% above the note's single run, within the 25% spread the note reports.

**The note's headline 1,024-row figures are its unrolled arm** (214 s to compile, 3.9 GiB). The landed engine never
runs that arm above 16 terms.

## The L4 column: the design's, kept, not re-measured

This is the note's §1.8 column (`/mnt/workspaces/Cells/fr43-20261123/out/gpu/`): the design snapshot `92e18df4` with
the cap raised in its process. It ran through the runner with every host check, on the NVIDIA L4 in float64, with its
host thread on a shared CPU.

**It was taken on the composite on a GPU, a path D336 found unqualified.** The composite's device checks failed their
GPU qualification (D330, D336). Since D336, the vector windows refuse the composite on a GPU
(`execution/vector_windows.refuse_unqualified_gpu`).

| Rows, sum | Compile s | ms per step | s per simulated s | Host peak RSS MiB | Card peak MiB | Error / largest |
| --- | --- | --- | --- | --- | --- | --- |
| 16, unrolled | 49.7 | 1.29 | 0.26 | 1,091 | 80 | 1.63e-5 |
| 256, unrolled | 352 | 5.6 | 1.12 | 2,865 | 100 | 1.63e-5 |
| 256, scan | 98.2 | 24.0 | 4.81 | 1,408 | 100 | 1.63e-5 |
| 1,024, unrolled | killed at the unit's 16 GiB host cap; no record | – | – | – | – | – |
| 1,024, scan | 377 | 105 | 20.9 | 2,848 | 124 | 1.63e-5 |

## Not measured

- **2,048 and 4,096 rows** (the profile in §1.6) are above the landed cap of 1,024, which refuses them at parse. They
  were not re-measured, and the cap was not patched.

## Records

- **Each figure:** `/mnt/workspaces/Cells/fr43-part1-gaps-20261124/perf/out/run-ROWS-rREPEAT.json`, with its log. The
  queue's log and the unit's memory peak (1.6 GB) are beside them.
- **`performance.json`** is the output of `scripts/profile_species_chain.py summary` over the twelve records, copied
  here unchanged. The design's CPU records (`out/v2`) and L4 records (`out/gpu`) are read beside them.
- **Provenance of this note.** FR-43 part 1's builder wrote this text. The harness refused the builder's own write of
  a report draft, and the user approved the lead committing the builder's text (24 November 2026, D372).
