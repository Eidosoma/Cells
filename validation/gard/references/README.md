# GARD component references (G2)

These are the independent references for the claims table in `docs/GARD_DESIGN.md` §6.1,
one module per row. Each states its derivation in its docstring, carries its planted
control, and is tested in `tests/unit/test_gard_references_*.py`. The comparison harness
(`harness.py`) runs every reference against an engine run's saved records.

**Independence.** This code was written without reading `src/cells/`, the engine's GARD
branch, or any file the engine's builder writes. Its inputs were:
- the design's §2 (taken as a specification to check, with every formula re-derived);
- §5.1–5.2 and §5.4 of the design (the record layout);
- §6.1 of the design (the claims table);
- decisions D186, D187, D192 and D197;
- the sources below;
- the earlier independent exact-enumeration scripts (16 November);
- the record names and conventions that the engine side declared, relayed by the lead.

Nothing imports `cells`; the code uses NumPy, SciPy and exact `fractions` only.

## Sources

Numbers are cited under D186. No text, figures or data files are copied.

- **S01, the preprint.** *Plastic heredity: Predicting and steering how inheritance
  breaks, returns, and persists*, v5.0, Zenodo, doi:10.5281/zenodo.22799362
  (concept doi:10.5281/zenodo.22143269), CC BY 4.0. The references use p. 10 (the kinetic
  contract), p. 11 (H, strict inheritance and F12), p. 68 (the exhaustive 4,096-sequence
  check) and Appendix F (contracts O-02 to T2-03; T2-02 is the direct-method contract).
- **PNAS 2000.** Segrè, Ben-Eli and Lancet, *PNAS* 97:4112 (PMC18166). Eq. 2 defines H
  and Eq. 4 is the rate law. The Fig. 1 legend gives the binomial split, p = 0.5.
- **BMC 2014.** Gross, Fouxon, Lancet and Markovitch, *BMC Evol Biol* 14:265 (PMC4357159).
  Eq. 2 is the rate law with a buffered reservoir. Its Methods orient beta_ij as the
  enhancement of type i by member type j, and fission gives two progenies of equal size.
- **J R Soc Interface 2018.** Lancet, Zidovetzki and Markovitch, *J R Soc Interface*
  15:20180159 (PMC6073634). It discusses GARD's out-of-equilibrium character: joining
  releases heat, and fission needs energy from outside.

## The kernel (`kernels.py`)

- **b_i(x) = 1 + (beta x)_i / N.** Both forms use this catalytic factor.
- **Single-event form** (S01 p. 10). The join is a_i^+ = k_f rho_i N b_i(x) and the leave
  is a_i^- = k_b x_i b_i(x). The preprint's values are k_f = 1e-2, k_b = 1e-4 and
  rho_i = 1/100 (held), with 100 types, beta = exp(-4 + 4Z) with the diagonal kept, and a
  founder of 40 distinct types.
- **Pair-consistent form.** The leave x -> x - e_i carries b_i(x - e_i), the factor of the
  join it reverses. So a_i^+(x)/a_i^-(x + e_i) = K_i rho_i N/(x_i + 1), which contains no
  beta.
- **Product measure.** That ratio is pi(x + e_i)/pi(x) for
  pi(x) = (N - 1)! prod (K_i rho_i)^{x_i}/x_i!.
- **Boundary rules.** N = 0 is absorbing, and b at the empty state is undefined.
  - The closed world and the kernel identities use `last_molecule_stays`.
  - In engine runs the rule depends on the form (see the amendment below).
    - The pair-consistent form uses `extinction_uncatalysed`: the last molecule leaves at
      the bare k_b.
    - The single-event form uses `extinction`: the last molecule's leave carries
      1 + beta_ii.
    - In both forms Phi(empty) = ln pi(empty) = 0, and that leave books q = -ln(K_i rho_i).
  - A world that names no rule is read per form. Every lineage row reports which rule it
    used.
  - In the preprint's lineage regime (masses 40-80) no rule ever acts.
- **The event guard** stops a lineage (the engine's rule; T2-02's guard would force a
  fission). The CRN replay follows the world's declared `guard_rule`.
- Float64 and exact rational versions are provided.

## The rows

| # | Claim | Reference and derivation | Planted control, and what the tests show |
| --- | --- | --- | --- |
| 1 | The exchange law (mean field) | `exchange_law.py`. At beta = 0, N(t) = N_0 e^{rt} with r = k_f Sum(rho) - k_b, and n_i(t) = n_i(0) e^{-k_b t} + (rho_i/Sum(rho)) N_0 (e^{rt} - e^{-k_b t}), by variation of constants. Per-type constants use expm. The propensities are linear at beta = 0, so the ensemble mean obeys this exactly. | A k_b 10% too large is caught by z-tests on mean N(t) and n_i(t). The registered design is 500 runs, 4 types, k_f = 1, k_b = 0.5, rho = (0.1, 0.2, 0.3, 0.4), founder (5, 5, 5, 5), at t = 0.5, 1, 1.5, 2. Its power is 0.9997 at alpha = 1e-3. |
| 2 | Catalysis is kinetic only | `time_rescaling.py`. With uniform beta = c, b = 1 + c in both forms (the pair-consistent leave needs N >= 2). Every propensity scales by s = 1 + c. Under shared uniforms the event sequence is identical, and times are divided by s, bitwise when s is a power of two. | A factor on joins only changes the sequence and the times; caught. The exact identity is checked in rationals for every state up to mass 6. |
| 3 | Local detailed balance (pair-consistent) | `detailed_balance.py`. ln(a^+(x)/a^-(x + e_i)) = ln(K rho N/(x_i + 1)) to within 1e-12, on 200 registered states of a 100-type preprint matrix. P1's square is checked in exact rationals. | The single-event form is refused as passive: its residual exceeds 1e-9. P1 at (1, 1) gives 0.012, 0.080, 0.113 and 0.117, and at (40, 40) from 1.7e-5 to 1.5e-4, matching §2.2. §2.5's 44/63 square is reproduced. |
| 4 | The stationary law in a closed world | `closed_world.py`. pi(x) is proportional to (N - 1)! prod theta^{x_i} C(M_i, x_i) for every beta, because detailed balance holds on every edge of the connected box N >= 1. The master equation is solved exactly in rationals for N_G = 2 and 3, and in float64 at larger M. The rank-one exception of §2.5 is checked exactly. | The single-event form departs. P2 (M = (8, 8), theta = 0.05, only beta_11 = 50) gives TV 0.579293, matching the design's 0.5793; only beta_12 = 50 gives 0.153475, against the design's 0.15. The pair-consistent form matches exactly: TV = 0 in rationals for the N_G = 2 and 3 test worlds, and 3e-15 in float at P2. |
| 5 | The SSA is exact | `ssa_oracle.py`, the host oracle: Gillespie's direct method with tau = -ln(u1)/a0 and the first j with prefix_j > u2 a0. Prefixes fold left in the declared channel table's order. It replays the run's own uniforms across fissions. At beta = 0 the total size is the linear birth-death process, with closed-form pmf, mean and variance (Kendall 1948). | A biased channel choice (leaves at 0.9 weight) is caught at the first differing event under common variates. In the ensemble, the mean test (power ~1) and the chi-square on the law of N(2) (power 0.99996) catch it. |
| 6 | The fission partition | `fission_partition.py`. The lineage's own splits must also obey the world's declared rule exactly (bounds, and size floor(fN) for the exact rule). Binomial: prod C(P_i, d_i)/2^{P_i}. Exact fraction: prod C(P_i, d_i)/C(N, floor(fN)). Both are checked against enumeration of every labelled assignment, in rationals. A conditional randomized-PIT chi-square (10 cells, alpha = 1e-3) is run on S_A, the daughter's count over the half-mass prefix of types. | A split at 0.55 is caught: p = 0.55, or floor(0.55 N) molecules. Registered design: parent 16 x 5 (mass 80), 400 splits, power >= 0.99 for both rules (the exact rule also by its size alone). Binomial splits presented as exact are caught. |
| 7 | Conservation | `conservation.py`. In exact integers at every row: count = founder + joined - left - discarded. Each fission discards exactly the unfollowed daughter. The trace, replayed from the founder, reaches every parent and reproduces the totals at every `row_event`. | A dropped molecule is caught at its row. A mis-booked discard is caught at the fission. |
| 8 | The thermodynamic ledger | `ledger.py`. Q(r) - Q(0) = Delta ln pi + W - S, with W_f = ln pi(P) - ln pi(D1) - ln pi(D2) and S_f = -ln pi(U). The hard check is convention-free: heat over each growth segment equals Delta ln pi~. `log_weight` = ln pi~ + C (one constant), the work and sink increments are checked, the trace is re-booked, and the residual is checked. The tolerance, u[E(2G + 72) + 8(E + 2)M + 64], is derived in the docstring. | A heat sign error is caught by the closure and by the booking. A work sign error is caught too. The single-event form's residual (the unsourced cycle work) is reported, not closed. |
| 9 | Streams | `streams.py`. Bitwise replay of every array, with run.json's identity fields (world, law, stream, conventions, channels, time) equal and any other differing field listed; batch-partition invariance; restart, compared bitwise from the checkpoint (whole run or tail); independence of branches, with distinct identities and no repeated 50-event prefix or uniforms. | A reused key (two branches sharing a stream under different declared identities) is caught. A reseeding restart is caught. |
| 10 | Observers | `observers.py`. H = x.y/(\|x\|\|y\|) against NumPy to within 1e-14. Inheritance is strict, H > 0.9, decided in exact integers: 100(x.y)^2 > 81\|x\|^2\|y\|^2. F12 (JOINT_BREAK_RUN3) has two independent predicates, a scan and the regex 0[01]*111, which agree on all 4,096 sequences with 2065 positives. That count is derived from the no-111 recurrence. | H = 0.9 counted as inherited is caught on exact-0.9 probes such as (45, 15, 15, 5) against (40, 0, 0, 0). A plain float `H > 0.9` is also caught, because rounding pushes some exact-0.9 pairs with irrational norms above 0.9. Off-by-one F12 detectors are caught. |

Statistical checks use alpha = 1e-3, registered in `common.py`. Each computes, before reading
any data, its power against its planted control. A design below 0.99 fails as
underpowered and never passes vacuously.

## The comparison harness

```
python -m validation.gard.references.harness make-probes OUT_DIR      # registered probe inputs
python -m validation.gard.references.harness run --roles ROLES.json [--rows 1,2,...] [--out REPORT.json]
```

**Exit status:**
- **0:** every requested row passed;
- **1:** a check failed;
- **2:** a record, role, declared convention or channel table is missing or malformed.

The status-2 message names the missing item. `standin.build_standin(dir)` writes a complete
stand-in record set from the host oracle (`lineage_oracle.py`) for dry runs. On the stand-in,
every row passes.

### Run bundles

A run bundle is one directory: `world.json`, `run.json`, `records.npz`, and `manifest.json`,
which is written last. A bundle without the manifest is refused.

- **The world** holds the ordered types, beta, the held rho, the k_join and k_leave
  constants, the founder, the fission rule (mass, guard, partition `binomial` with p or
  `exact_fraction` with fraction), the continuation rule and the optional `units`.
- **The run** holds:
  - the world id, and founder `"world"`;
  - `law.form` (`single-event` or `pair-consistent`), `law.check_verdict` and the mode;
  - the stream identity;
  - `ssa_convention` (`tau`, `select`, `uniform`);
  - `channels.rows`, the declared channel table;
  - the optional `time` block, the ledger conventions and the end status.
- **The arrays,** in the row base (the start row, then a parent and a followed daughter
  per fission), are:
  - row arrays: `row_time`, `row_event`, `assembly_count` [row, type, 1], `joined_total`,
    `left_total`, `discarded_total`, `exchange_heat_kT`, `fission_work_kT`,
    `discarded_free_energy_kT`, `log_weight`, `ledger_residual_kT`, `occupant` and
    `generation`;
  - the fission table: `fission_time`, `fission_slot`, `fission_parent`,
    `fission_daughters`, `fission_followed` (0 or 1), `fission_split` (daughter 1),
    `fission_similarity` [f, 2] and `fission_partition_counter`;
  - the trace: `event_time`, `event_channel` (codes read through the channel table) and
    `events_per_growth`;
  - in diagnostic mode, also `event_uniforms` [event, 2].

`records.WORLD_FIELDS` and `records.RUN_FIELDS` are the only places that know the JSON key
layout (the run's `restart` and `t_end` included). Replays compare the canonical
`records.IDENTITY_FIELDS`; a field neither run declares is reported as absent. When the engine's container is fixed, only these two tables change, plus the
`ssa_convention` value strings in `ssa_oracle.DECLARED_BY_ENGINE`.

### Roles

| Role | Content | Rows |
| --- | --- | --- |
| `lineage`, `lineage_single_event` | One single lineage per form, from one world and one founder | 7, 8, 10 (`lineage` also 5, 6 and 9) |
| `lineage_diagnostic` | `lineage` rerun in diagnostic mode (events must be unchanged), with `event_uniforms` | 5 |
| `rescale_beta0`, `rescale_betac` | beta = 0 and uniform beta = c, one founder, shared stream keys | 2 |
| `beta0_ensemble` | A list of bundles of the registered design, without fission, reaching t = 2 (or declaring `t_end`) | 1, 5 |
| `replay`, `batched`, `restart` (a list), `branches` (a list) | A replay of `lineage`; the same world run inside a batch; restarted runs declaring `restart.row`, `restart.event` and `restart.fission`; at least two branches from one landmark, in diagnostic mode (`event_uniforms` and `partition_uniforms` required) | 9 |
| `kernel_probe` | Probe: `join_*`, `leave_*` and `leave_up_*` (the leave of type i at x + e_i), for `*` = `pair_consistent` and `single_event`, on the registered 200 states, with the inputs echoed and `check_verdict` per form | 3 |
| `closed_world` | Probe: `states_*`, `join_*` and `leave_*` with the held supply rho = 1, for `*` = `{p2_beta11, p2_beta12, three_types}_{form}`. The harness converts them to closed-world rates and drops the leaves at N = 1, because the claim concerns the chain on N >= 1 | 4 |
| `partition_probe` | Probe: `parents_*` and `splits_*`, for `*` = `exact_fraction` and `binomial`, giving 400 splits of the registered parent | 6 |
| `observer_probe`, `f12_table` | Probe: the engine's `H` and `inherited` on the registered pairs; `verdicts` [4096] with the declared `bit_order` | 10 |

A probe is a directory with `probe.json`, `probe.npz` and `manifest.json`. Its inputs come
from `make-probes`, which regenerates them deterministically from registered seeds through
NumPy's `Generator` (`inputs.json` records the NumPy version).

**Run `make-probes` and `run` in the same environment** (`venv-cpu`). The harness regenerates
the inputs in-process and requires each probe's echo of them to match bitwise. A different
NumPy fails loudly; it never matches silently.

A world that does not declare `rules.boundary` is read as `extinction_uncatalysed`, the
engine's declared convention. Every lineage row's detail reports the rule and whether it
was declared.

Accepted tokens (anything else is refused with status 2):
- `law.check_verdict`: `passive`, or `refused_as_passive`, `refused`, `driven` or
  `not_passive`;
- the probe's `boundary` and `rules.boundary`: `last_molecule_stays`, `extinction` or
  `extinction_uncatalysed`;
- `rules.fission.guard_rule`: `stop` or `fission`;
- `bit_order`: `lsb_first` or `msb_first`;
- partitions: `binomial` or `exact_fraction`.

Other conventions:
- If the world's types carry transfer constants K, they must equal k_join/k_leave.
- `fission_followed` is 0 for the first daughter and 1 for the second.
- Partition streams are keyed by the parent's carrier key (`fission_partition_counter`
  is 0). So row 9 also flags repeated partition uniforms across branches.
- Events after the last fission are covered by no saved row. Their heat is checked only
  if an end row is saved.

### The engine's layout

`engine_layout.py` and `records.adapt_engine_world`/`adapt_engine_run` read the engine's
role set as its FORMAT.md describes it (`cells.assembly_lineages@1`).

**World and run records:**
- **World:** `{format, id, world, derived}`.
  - β is `world.law_data.catalysis_matrix`; without it, β = 0.
  - ρ is `world.supply`; k_join and k_leave come from `derived`; K is
    `world.types.transfer_constant` and must equal k_join/k_leave.
  - The event guard is `experiment.growth_event_limit` in `resolved_config.json`, and the
    lineage stops at it.
- **Run:** the verdict is `law.check.admitted_as`, and `law.form` is the form. A run with
  no rate-factor law is read as form `none`, the exchange law alone.
- **SSA:** the prose in `run.json` `ssa` and `stream.uniform` maps onto the oracle's tokens
  (`records.ENGINE_SSA`). Any other wording is refused.

**Records and groups:**
- **Row base:** start, (parent, daughter) per fission, then a final end row (`row_kind`
  0/1/2/3). The end row lets conservation and the ledger check the last growth too.
- **Groups:**
  - `batched/batched.json`: lane 0 is the lineage's definition;
  - `restart/restart.json`: each case is a stopped run and its continued run, compared
    bitwise with the uninterrupted run;
  - `branches/branches.json`: the branch runs;
  - `beta0_ensemble/beta0_ensemble.json`: the ensemble's members.

**Probes:** each is `probe.json` + `probe.npz`, with arrays `<form>.<array>` and the
registered inputs echoed as `input_*`. Each echo must match the inputs this package
regenerates.
- The kernel probe's verdicts come from the lineage runs.
- The observer probe gives H only; the per-pair inheritance marks are reported missing.
- The F12 table's explicit `sequences` and `certified_at` are checked against both
  predicates.

**Ensembles off the registered design:** a β = 0 ensemble that does not follow the registered
design is judged at the registered times. It fails as underpowered if it cannot catch its
planted control. Its agreement with the closed form at world-scale times (10, 20, 30, 40) is
reported beside the verdict and never decides it.

## Amendment, 17 November 2026: the single-event form's last leave

- **What changed.** In the single-event form, the leave at N = 1 now carries the factor
  1 + beta_ii (rule `extinction`). That is the preprint's kernel, which counts the leaving
  molecule. The pair-consistent rule is unchanged: its last molecule leaves uncatalysed.
- **Why.** The earlier rule followed a relayed convention: "the last molecule leaves
  uncatalysed, in both forms". The lead has since said that relay was wrong for the
  single-event form. The rule now follows `docs/GARD_DESIGN.md`, written before any engine
  run, at:
  - line 43 (cited by the lead): the pair-consistent factor equals the published one to
    O(1/N), except under strong self-catalysis;
  - lines 260-262: the pair-consistent form retains strongly self-catalytic types a little
    more, because their leaving is no longer self-catalysed;
  - line 318: in the pair-consistent form, the leaving molecule does not catalyse its own
    leave.
- **When.** The change was made after report-2 (the provisional set 6af93a51) showed the
  disagreement on the 4 mass-1 probe states. Read with the amended rule, the engine's
  single-event table matches there exactly. report-2 is kept unchanged.
- **Planted control.** A single-event kernel whose last molecule leaves uncatalysed must fail
  row 3 (`tests/unit/test_gard_references_row03_04.py`).

## What could not be confirmed from the sources

- **The pair-consistent form is the design's correction, not a source's kernel.** The
  original papers give the rate law and no event rates, as §2.5 says. Only the preprint's
  single-event form is sourced (S01 p. 10). The PNAS 2000 scheme draws Poisson changes
  on the net rate.
- **P2's third value (0.004, a small lognormal pair) and all of P3 depend on the design's
  matrices, which are not available here.**
  - On three matrices of my own (preprint contract, 200 fissions, single-event form), the
    mean drive per join is 2.3-2.5 k_BT, against 1.97 in §2.1. The propensity-weighted
    |bias| is 0.017-0.025, against 0.023.
  - The tail scales with the diagonal: max |bias| is 3.5 at a diagonal of 1354, against
    4.0 at 2618.
  - These numbers agree in size, but none of them reproduces the design's.
- **P4 (CPU against GPU) and the composed checks are outside the ten rows.**
- **"S5's R-ops form" (§2.4) is not in the reading list.** The 200 probe states are
  this package's own, registered by seed.
- **The PNAS 2000 constants (k_b = 1e-5, finite pool) differ from the preprint's
  (k_b = 1e-4, held rho).** §2.1's numbers are the preprint's.
