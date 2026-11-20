# Fuel, option (d): OL5's independent references

**Registered 20 November 2026, before any engine fuel world has run.** These are the independent
references for the fuel note's checks (§5) and option (d)'s own references (§3 (d)), with its nulls
and the optional control (d0). The lead registers them with a tag before any engine fuel world runs
(D245's order: no fuelled world runs before OL5's references for it are registered, and that
includes (d0) and held-block worlds).

## The only source

`docs/ORIGIN_OF_LIFE_FUEL_DESIGN.md` at the git tag **`ol4-fuel-note-2026-11-20`** is the only
design source. For conventions I also read, at that tag:
- `docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md`;
- OL5's earlier references in the parent folder.

The lead's rulings of 20 November 2026 on my plan (Q1–Q6) are recorded in `designs/ol4_design.json`.
- **Q1.** "Zero drive" is μ_F = μ_W, with held potentials including their activities.
- **Q2.** Every arm is compared by total variation, and modality is only reported.
- **Q3.** V1 (vesicle worlds) is in this registration; the composed population run comes later.
- **Q4.** The switching time is compared from the engine's rate table.
- **Q5.** The driven-law refusal is the builder's registration test, so OL5 registers no world for it.
- **Q6.** A constructed set stands in for C4b.

**Nothing here was read or imported from the engine side:**
- `src/`;
- the builders' `validation/assembly_lineages*/`;
- the note author's desk probe;
- other agents' runs;
- any engine output.

The code imports NumPy, SciPy, `fractions` and OL5's own modules only. OL1's exact law
(`laws.Law`) and OL2's geometry (`ol2.Law2`) are reused unchanged. Nothing registered for OL1, OL2
or OL3 was edited.

## What the registration holds

- **`designs/*.world.json`:** worlds without geometry (`ool_references.world@1`, exact rationals
  beside every float).
- **`designs/*.world2.json`:** vesicle worlds (`ool_references.world2@1`, with a
  `transition_state_factor` list on membrane steps and pool steps over held places).
- **`designs/*_probe_states.json`:** kernel probe states, with the registered cycles.
- **`designs/*_states.json`:** every state of each finite world.
- **`designs/refusals/`:** the refusal declarations.
- **`designs/ol4_design.json`:** rows, roles, runs, tolerances, the switching starts, the search's
  pick, and the planted controls' magnitudes.

`design.write_all()` generates every file, and the test holds the committed copies byte-equal to
it. One convention pair is probed: (multinomial, kept). This follows D215; the core step
B + L → 2 L has L on both sides, so it is singular under multinomial_less_one outside probe
worlds.

## The worlds

Every value is a declared test parameter, unsourced.

| World | What it is | Rows |
| --- | --- | --- |
| `ol4_fd_kernel` | (d) without geometry. F and W held (drive μ_F − μ_W = ln 24). B, S, L1 and L2 each have pool and membrane places. Steps: f1: F + S → B + W in the pool; five joins; a_i: B + L_i → 2 L_i, catalysed by L_i (β = 5/2); d_i: L_i → S | OL4-1, OL4-2, OL4-3 |
| `ol4_fd_heldB` | No fuel; B and S held at μ_B − μ_S = ln 12 (the held-block world) | OL4-1 to OL4-4 |
| `ol4_fd_d0` | (d0): B and S held at μ_B = μ_S. With fast exchange this gives the note's C4 values (x_B = x_S = 9/20, ρ = 1/9, β = 20, k2/k1 = 1/100) | OL4-1 to OL4-4, OL4-8 |
| `ol4_fd_null` | The dividing null (L6): μ_B = μ_S at ρ = 2/3 (x_B = x_S = 3/10) | OL4-1 to OL4-4, OL4-8 |
| `ol4_fd_finite` | F and W finite: the fuel's free energy is stored in F. Closed in both moieties | OL4-1, OL4-3 to OL4-5 |
| `ol4_fd_heldF` | F held, W finite (the waste accumulates) | OL4-3, OL4-4 |
| `ol4_fd_ness`, `_ness_beta0`, `_zero`, `_zero_beta0` | One chemistry, closed in the block at M = 15 (15,488 states), F and W held, chosen by the exact search (below). Arms: driven with β = 6; driven with β = 0; μ_F = μ_W with β = 6; μ_F = μ_W with β = 0 | OL4-5 to OL4-7 |
| `ol4_fd_edge`, `_edge_beta0` | The strongly downhill regime at M = 12, a reported counter-example (below) | OL4-6, OL4-7 |
| `ol4_fv_kernel` | V1: (d) in a vesicle. Bilayer geometry (q = 3·10⁻¹⁷ m², equal quanta), an osmotic lumen with one impermeant solute, insertion_area joins, held fuel and waste (drive 2.5 + ln 3), the floor and lysis | OL4-1, OL4-2 |
| `ol4_fv_closed` | V1: one closed vesicle at μ_F = μ_W, 8 block molecules. Two impermeant lumen molecules put the kink between tense and floppy at W = 5; it cannot lyse | OL4-5 |

## The rows

| Row | Claim (note) | Reference | Tolerance | Planted, and what the reference shows |
| --- | --- | --- | --- | --- |
| OL4-1 | Pair identity with fuel (§5.1) | ln a⁺ − ln a⁻ = −ΔF + w, with w = −Σ_held ν μ_h and μ_h = μ°_h + ln(c_h/c0). Exact in the reference. Also the forward form k·g(m)·(N(m) + 1)·θ⁺ and the reverse rates (`kernel.py`). Vesicle form in `vesicle.py` | 64u(4 + Σ\|ln a\| + \|ΔF\|); vesicle 10⁻⁸ in ln a, forward 10⁻¹² | No reservoir work (residual ln 24 = 3.18); work sign (6.36); held activities dropped (identity 1.10, forward 0.41); extent N − r + 1 (forward ln 2 = 0.69); factor at own state (0.44); forward-only catalysis (1.25); fuel term dropped, finite fuel (identity 4.38). Vesicle: no reservoir work 3.60; work sign 7.20; extent N − r + 1 (forward 0.001); factor at own state (identity 0.0019); factor dropped (forward 0.67) |
| OL4-2 | The cycle's drive (§5.3) | Σ ln(a⁺/a⁻) around registered cycles. The five-step fuel loops (via L1 and L2, two orders) give ln 24; held-block loops give ln 12 (`ol4_fd_heldB`) or 0 (`d0`, `null`); exchange loops a1 d1 d2⁻¹ a2⁻¹ give 0. Squares close at any drive | 64u(rates + Σ\|ln a\| + \|target\|) per cycle; vesicle 10⁻⁸ | Wrong sign: off by 2·ln 24. No work: off by ln 24, while Kolmogorov's squares pass. Factor at own state, and forward-only catalysis: the exchange loops fail |
| OL4-3 | Closure with fuel (§5.2) | OL1's `ledger.check_ledger` on the replayed trace (heat and work re-booked per event), plus the payers' split W = Σ_h μ_h·supplied_h | OL1-5's derived bound; payers 2(16uE(1 + max\|μ\|) + 4uΣ\|μ s\|) | Fuel term dropped from F (finite fuel), and no reservoir work: closure fails. Payers swapped: W off by twice its value |
| OL4-4 | Moieties (§5.5) | Σ M·n − Σ_held M·supplied is constant for the block and the fuel. The supply record equals its re-derivation from the trace | Exact integers | All supply ignored (held F with finite W; held block); the waste's supply ignored (both held, §8's plant). With F and W both held, "all supply ignored" cannot bite and is not registered there |
| OL4-5 | True equilibrium (§5.4) | At μ_F = μ_W, the engine table's stationary law against exp(−F)/Z. The same with β = 0, with finite fuel, and in a vesicle across its kink. The (L1, L2) law peaks only at \|a − b\| ≤ 1 (product form) | TV 10⁻¹⁰; vesicle 10⁻⁷ | Factor at own state, and forward-only catalysis: the law moves (TVs in the design). A dropped factor does not move it, as it should not (catalysis is kinetic) |
| OL4-6 | Heat at stationarity (§5.6) | The driven law against the reference's. J = Σπ(a⁺ − a⁻) for f1, and the mean heat rate = J·A (an identity at stationarity). On a long run (200,000 events): \|Q − N_net·A + ΔF\| within the closure bound, and a z-test of N_net/t against J, using the exact variance rate and start bias (Poisson equation) | TV 10⁻⁹; J and heat 10⁻⁸ relative; \|z\| ≤ 3.29 | No reservoir work: the law and the flux move. Flux counted without its reverse events (a reader's error): the heat identity fails pathwise |
| OL4-7 | Modality and switching (§3 (d)) | The modality is reported under the registered definition. The mean switching time from the L1-rich to the L2-rich region (shares ≥ 3/4 and ≤ 1/4, with L ≥ 2) is solved exactly on the engine's generator, from the registered start | Switching time 10⁻⁷ relative | — |
| OL4-8 | §2.3's closed form, the nulls and (d0) | Exact rationals: the condition, f±, A*, γ. An independent count from the raw rates (Sturm's theorem). The nulls are proved and checked on 4,000 seeded sets. Reproduces the note's numbers: C4 f = 0.082 and 0.918, γ = 1.055 (note: 1.06); C5 A* = 6.59 and 3.42 (note: 6.6 and 3.4); β ≥ 655,680 on the zero-affinity line at ρ = ¼ (note: 6.6 × 10⁵); β ≥ 8 in the feed regime | Exact | Three wrong closed forms disagree with the raw count on the sample: 2 for 4, T for T², and C without its 1·e^Δ1 term |
| OL4-9 | The fuel line's refusal (§6, L1) | A factor on the pool-only step f1 is refused. The fuel parser runs this after OL1's parse, so every earlier message stands | — | The declaration accepted |

**The constructed C4b-like set (Q6).** It is labelled as OL5's construction, not the note's C4b:
- E1 = E2 = 1/8, x_S = 1/20, T = 1/2, k1 = k2 = 1, β = 32, and x_B = 67/480;
- the even mixture's r(T/2) = 0 exactly; the set is bistable at A = 5.19 k_BT, and its stable
  states grow at γ = 0.32.

## Findings

**1. The β = 0 null is not always unimodal in small, strongly downhill worlds, and switching there
is drift, not catalysis.** The lead records this for OL9's registration, and it qualifies §3 (d)'s
wording. In `ol4_fd_edge` (e^Δ1 = e^Δ2 = 1/8, k2/k1 = 1/10, held fuel):
- both arms put their two modes on the edge where one amphiphile is absent;
- the β = 0 arm does so as well as the catalysed arm;
- the cause is fixation by drift: S re-forms either amphiphile only rarely.

In the scratch scans at M = 8 to 14, the mean switching time did not grow with size in either
arm. At ln 2981 ≈ 8 k_BT, ln τ was:

| Arm | M = 8 | M = 10 | M = 12 | M = 14 |
| --- | --- | --- | --- | --- |
| β = 0 | 7.60 | 7.56 | 7.45 | 7.30 |
| β = 20 | 7.17 | 6.99 | 6.82 | 6.68 |

So in small worlds, "unimodal at β = 0" holds only where re-formation from S and the reverse of
the core step outweigh drift. For U5's spontaneous arm (a few tens of amphiphiles), the β = 0
null may itself switch by drift, so its switching should be measured in the same world.

**2. Inside peaks need a world that is bistable at large size.**
- In the M = 10–12 scans, some worlds showed two shallow inside peaks (dip 0.96–0.99). They had
  one mode at M = 14: their large-size limit is not bistable.
- The registered `ol4_fd_ness` was chosen in the mean-field limit first (its own x_B, x_S and T
  satisfy §2.3's condition, with f₋ = 0.36), then confirmed exactly at M = 15:

  | Arm | Modes | Mean amphiphiles |
  | --- | --- | --- |
  | Driven, β = 6 | (1, 10) and (10, 1), dip 0.57 | 10.6 |
  | Driven, β = 0 | One, at (3, 4) | 7.2 |
  | Zero drive | One, at (4, 4) | 8.7 |

- Worlds in the same family with the drive raised to ln 64 put their peaks on the edge at M = 14
  and 15, with dips of 0.18–0.45.

## Using the rows

- **The canonical record layout** is in `harness.py`'s docstring. An adapter maps the engine's own
  records onto it once the family's format for fuel exists.
- **Running the rows:** `python -m validation.ool.references.fuel.harness --records DIR`, which
  exits 0 (pass), 1 (a check failed) or 2 (a record is missing or malformed).
- **A stand-in:** `python -m validation.ool.references.fuel.standin --out DIR [--planted FORM]`
  writes stand-in records from the references themselves.
- **Run time:** the full rows need several sparse solves at 15,000 states, about 10–15 minutes on
  one core.

**What the engine writes:**
- kernel probes (`a_plus`, `a_minus`) at the registered states of five worlds, and tables over
  every state of seven finite worlds;
- the same for V1, with lysis flags, over every declared step, pool steps included;
- six ledger runs of 2,000 events and one run of 200,000 events, each with a per-held-place supply
  record (`supplied`; the engine's `reservoir_supplied`);
- the refusal.

## Evidence

The staging folder is `/mnt/workspaces/Cells/ol5-fuel-references-20261120/`:
- **`plan-scratch-20261120/`:** the plan's scratch solves (finding 1's numbers).
- **`evidence/search/`:** the search's tools and outputs:
  - the vectorised rates are checked against `FloatRates` to 2·10⁻¹⁶;
  - `meanfield.py`;
  - the candidates at M = 14 and 15.
- **`evidence/register_magnitudes.*`:** the registered magnitudes and the reference's own numbers.

The test is `tests/unit/test_ool_references_fuel.py`.
