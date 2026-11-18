# Origin-of-life engine: component references (OL5)

**Registered 17 November 2026, before any engine output exists.** These are the independent
references for the component claims of `docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md` §7.1–7.2, milestone
OL5 (§8). This registration covers OL1's claims in full; OL2–OL4 follow in that order, with the
priority D212 sets (below). The model is G2's GARD references (`validation/gard/references/`).

Each module states its derivation in its docstring and carries its planted controls. The tests are
`tests/unit/test_ool_references_*.py`. The harness (`harness.py`) runs every reference against an
engine's saved records.

**What the registering commit holds.**
- The closed menu of convention tokens: `designs/ol1_conventions.json`.
- The registered worlds and the refusal declarations: `designs/*.world.json` and
  `designs/refusals/`.
- The probe states:
  - `designs/ol1_kernel_probe_states.json` (589 states of `ol1_wa`; 592 since amendment 4);
  - `designs/ol1_closed_world_states.json` (387 states of `ol1_wa_closed`).
- The design file, `designs/ol1_design.json`, and the reference modules.

The registering commit is 08870ef6. The tests, the harness and the stand-in followed on this branch
the same day:

| Test file | What it holds | Planted controls |
| --- | --- | --- |
| `test_ool_references_registration.py` | Every committed design file equals its generator; every world parses; every registered refusal is refused; the menu refuses missing, unknown and refused tokens | A changed byte; a float that is not its exact value; each registered defect |
| `test_ool_references_laws.py` | Exact Kolmogorov, the products' rule against F, and the edge identity, on a slice of the probe under all four token pairs; the extinct boundary's k⁻ in both directions (`ol1_boundary`); a float64 kernel within the registered tolerances; the float rates against the exact law; E1 and E2 | Every row OL1-1 and OL1-4a form, each by its named check, under both probed pairs; a literal zero at the boundary |
| `test_ool_references_closed_world.py` | 1,312 exact edges; stationary laws within 10⁻¹³; catalysts that leave the law unchanged | Five planted laws and the other measure depart; a rate leading outside is caught |
| `test_ool_references_mass_action.py` | The Riccati form against SciPy's Radau; the master equation's O(1/X) approach; the registered null means and powers; the test on exact samples | Wrong sign, S → T, and biased selection fail; an underpowered design is refused |
| `test_ool_references_runs.py` | Replay, ledger closure, moieties, the bitwise time rescaling, and streams on host runs | Biased selection, a heat sign error, dropped work, an update off by one, a forward-only factor, a reused key |
| `test_ool_references_harness.py` | Every row passes end to end on the stand-in (exit 0) | A planted form, a literal zero at the boundary, or a short rescale pair fails its row (exit 1). Exit 2 for: a ladder below its registered size; one convention pair alone, or one twice; a ledger run without its registered rows; a missing role, manifest or token; a changed echo |

## Independence, sources and a disclosure

**Written without the engine.** Nothing here imports `cells` or reads `src/cells/`, the builder's
branch or its worktree. The code uses NumPy, SciPy and exact `fractions` arithmetic only. Its inputs
were:
- the design note: §0.1, §0.2a, §2.1–2.5, §3, §4, §5, §7 and §8;
- decisions D186, D187, D192, D197, D199, D201, D212 and D215;
- `docs/SOTA_ORIGIN_OF_LIFE.md`;
- G2's README and harness on main;
- the design lane's probe outputs (`/mnt/workspaces/Cells/ool-design-20261117/`, the README and
  `probe_ldb.out` only), for E1's and E2's parameters.

**Disclosure (17 November 2026).** Before registering, I read the OL1 builder's draft format. The
lead relayed the file, which held declarations and forms only, with no values.
- I adopted its token names.
- I replaced my own volume-based encounter forms for membrane steps with its `count_on_m` form,
  after re-deriving that form's key property myself. The property: the reverse rate derived from F
  equals the same rule applied to the products, for every order up to three on each side and under
  both measures. `laws.py` derives it. The full check, exact on all 4,123 probe state-step pairs,
  is the design-time evidence in `/mnt/workspaces/Cells/ool-references-20261117/evidence/`
  (`exact_wa.py`, `exact_wa.out`). `test_ool_references_laws.py` holds it on a slice of the probe.
- My volume-based forms lacked the property for termolecular steps.
- The lead's rulings (§0.2a) govern wherever they differ from the draft.
- One point of mine became a ruling. Under `extinct`, the last molecule's rate is the pair rule in
  its cancelled form, which gives G1's k⁻ in either direction. Evaluating it through F with
  F_mem(empty) = 0 would give a literal zero, and that is an error. (§0.2a as amended on the same
  day.)

**Sources.** Numbers are used under D186 and D201; no text, figures or data are copied.
- Gillespie 1977 (the direct method) and Kurtz 1972 (the large-system limit), from memory, as the
  design cites them.
- The design note's E1 and E2 probes, reproduced exactly (row OL1-2).

## The conventions: a closed menu (§0.2a)

Every bundle and probe declares every token. A missing or unknown token is refused (exit status 2).
There are no defaults.

| Key | Tokens | Meaning in the references |
| --- | --- | --- |
| `free_energy_form` | `discrete` | F uses ln n! exactly. `continuum` (Stirling) is refused, as the exact kernel refuses it |
| `condensed_measure` | `multinomial` (c = 0), `multinomial_less_one` (c = 1) | The membrane's measure −ln (N − c)! + Σ ln n_i!; 0 at N = 0 |
| `membrane_kinetics` | `count_on_m` | Membrane activities Π ff(n_i, α_i)/ff(N − c, r) at the firing state; extent N(m) − c + 1 on m |
| `lumen_volume` | `declared` | Accepted; OL1's worlds have no lumen |
| `empty_catalyst_phase` | `uncatalysed` | g = 1 where the membrane is empty at m. Only the membrane catalyses (§0.2a); a dilute catalyst is refused |
| `last_molecule` | `kept`, `reversible` (with c = 0), `extinct` (with c = 1) | `kept` (amendments 4 and 5): rate zero only for a pair whose step changes the membrane's count and one of whose end states has an empty membrane. A step in which the membrane takes no part fires at its own rate under every token, and a pool step at a probe state with an empty membrane fires at the pool's mass action (§0.2a as reworded, main bbcbec69). `extinct`: a channel whose result empties the membrane fires at the pair rule's cancelled form, E(m)/ff(N − 1, r) → 1/ff(N − 1, r − 1), in either direction. It is one-way, and its heat is booked against F_mem(empty) = 0. Under every token, a 0/0 membrane factor takes the same cancelled form (amendment 4) |

- **Dilute phases** use mass action scaled by X = N_A V c0: activity ff(n, α)/X^α and extent X.
- **Coverage.** The references cover all four admissible (measure, last-molecule) pairs.
- **Probes.** The registered probes ask for two pairs: the physical worlds' `multinomial` with
  `kept`, and the GARD limit's `multinomial_less_one` with `extinct` (§0.2a, D215).

## The registered worlds (`designs/`)

The worlds are written in the family's vocabulary: places `species@phase`, a `locus` per step,
`standard_mu_RT` per phase kind, `standard_concentration_mM`, `volume_L` and `forward_rate_per_s`.
Every float sits beside its exact value: rationals, with potentials as exp(−μ°). So the references
decide identities exactly, and `world.parse_world` refuses a float that is not its exact value to
rounding. `registered.py` generates every file, and a test holds the committed files byte-equal to
the generator.

| World | Content | Rows |
| --- | --- | --- |
| `ol1_wa` | A membrane (A, B, C, D, E, S) and a pool (A held at 1/4 mM; S and T finite; X = 8; c0 = 1 mM). Seven steps: x1 a join from the held pool (catalysed by C); x2 a join from the finite pool; p1, 2 S → T in the pool; r1, A + B → C; r2, 2 A → D; r3, A → E catalysed by E (autocatalysis), C and D (inhibition, β = −1/2); r4, A + B + E → C + E (termolecular, catalyst on both sides, parallel to r1). Regular mixing on seven pairs | 1, 4a, 4c, 5, 6 |
| `ol1_wa_closed` | `ol1_wa` without the held species and x1: closed, with moieties a, b and s conserved. 387 states from its initial state; the membrane is never empty | 2, 3 |
| `ol1_wa_closed_uncatalysed`, `ol1_wa_closed_x2` | The same, with no catalysts; and with every forward rate constant doubled | 3 |
| `ol1_wb_m{5,20,80,320}` | 2 S → T in the pool, k = 1/2 s⁻¹, K = 1, X = M, 2M molecules of S at the start; an inert membrane of three L. One-dimensional (M + 1 states) | 4b |
| `refusals/refuse_*` | `ol1_wa` with one defect each: a coefficient off by one; four reactant molecules; four product molecules; a coefficient of 1.5; a dilute catalyst; a nonzero χ diagonal; a step that changes nothing; a wrong locus; a step carrying its own ΔG° | 4d |

`design.py` generates the machine-readable files, and a test holds each committed copy byte-equal to
its generator:
- `designs/ol1_design.json`: the rows, roles, seeds, sizes, statistics and planted controls;
- `designs/ol1_conventions.json`: the token menu, with each token's meaning and the probed pairs;
- the two probe-state files.

## The rows (OL1)

Statistical checks use α = 10⁻³ family-wise and require a power of at least 0.99 against each
planted control, computed before any record is read (`common.py`). An underpowered design fails;
it never passes vacuously. Exact checks register their tolerance's derivation and the planted
controls' margins.

| # | Claim (§7.1) | Reference and derivation | Planted controls, and what the reference shows on the registered inputs |
| --- | --- | --- | --- |
| OL1-1 | Every channel keeps local detailed balance | `detailed_balance.py`, `laws.py`. On the engine's kernel table at 589 registered states of `ol1_wa` (592 since amendment 4) (seed 2026111701; 24 base states with counts at most 9, every square's corners, and boundary states), three checks run. (1) Kolmogorov's criterion on 360 squares and 133 parallel two-cycles (on the amended 592 states: 360 and 135). It needs no convention and cannot be met by comparing the engine with itself. (2) The identity ln a⁻(n′) − ln a⁺(n) = F(n′) − F(n) − w under the declared tokens. (3) The reverse rates, the extinct boundary's cancelled form included. The tolerance is 64u(8 + Σ\|ln a\|) per cycle, below 3·10⁻¹² here. In the reference itself every square and two-cycle closes exactly (RatExp), under all four token pairs | Under (multinomial, kept): the factor at each direction's own state fails Kolmogorov (max 0.0074, 124 cycles) and the identity (1.39 since amendment 4, 0.125 before: r3 at a lone A now fires, with g = 1 forward against 4 at its reverse's own state, ln 4). Catalysis on the forward channel only fails Kolmogorov (0.057). A one-sided off rate (r3's reverse × e^{x_D}) fails Kolmogorov (0.061). A wrong sign of ΔF fails the identity (10.6). A dropped c0 fails the identity (6.91). The other measure fails the identity (0.693). A wrong last-molecule token fails the boundary rates. The honest table's largest residual is 2.7·10⁻¹⁵ |
| OL1-2 | A closed world relaxes to exp(−F/k_BT) | `closed_world.py`. In the reference, a⁺(n)w(n) = a⁻(n′)w(n′)e^{w} holds exactly on every edge of `ol1_wa_closed` (1,312 edges, all four token pairs). The world is connected, so π = w/Z is its unique stationary law. On the engine's table, the generator's stationary law (sparse LU) must lie within total variation 10⁻¹⁰ of exp(−F)/Z, and Kolmogorov must hold on all 1,821 squares and 243 two-cycles | The planted stationary laws depart: own-state factor TV 0.083; forward-only catalysis 0.30; one-sided off rate 0.0079; dropped c0 0.997; wrong sign 0.997; the other measure 0.035. Honest: 5·10⁻¹⁶. **The design's probes reproduce exactly.** E1 gives TV 0.0829822 with cycle ratio 143/128. The kinetic split (forward constants 1, reverse 1/K) is identified by reproduction: reverse constants 1 with forward K give 0.0842. E2 gives TV 0.5407884 with ratio 2/3; its per-contact ω is not §2.2's form, so it tests the enumerator only |
| OL1-3 | Catalysis is kinetic only | `catalysis.py`. (3a) The closed world with its catalysts and without them must both relax to exp(−F)/Z. (3b) The closed world and its rate-doubled variant, under one stream identity, must fire the identical channel sequence (500 events) at exactly half the times. Doubling is exact in floating point, so the comparison is bitwise | (3a) Forward-only catalysis departs (TV 0.30). (3b) A factor on forward channels only changes the sequence |
| OL1-4 | Mass action with registry potentials | `laws.py`, `mass_action.py`, `ssa_oracle.py`, `world.py`, in four parts. (a) The forward form, on the kernel probe, under the declared tokens. (b) The large-system ladder on `ol1_wb_m{5,20,80,320}`: 2,000 runs per rung to 2 s, means at 0.25, 0.5, 1 and 2 s. Each mean is z-tested against the **exact master-equation mean** of its rung, Bonferroni over 16 tests (z = 4.003). The ODE is not the null, because the exact mean differs from it by O(1/X). The ODE's closed form (Riccati) and SciPy's Radau agree to 2.5·10⁻¹⁴. The gap falls fourfold per rung: −0.0188, −0.0046, −0.00114, −0.000285 at t = 0.25 s. (c) The host oracle replays a diagnostic run under common variates. (d) Every registered refusal is refused at parse, and every moiety is conserved at every row | (a) n^α for the falling factorial (0.693), N^r for the draw's normaliser (1.5 since amendment 4, 0.186 before), the extent without its offset (0.693; an error under c = 0 only, since under c = 1 it is the rule) and a dropped c0 (6.91) each fail the forward form. (b) Family power at 2,000 runs: n² for n(n−1) 0.998; dropped c0, wrong sign, S → T run for 2 S → T, and selection biased against reverse channels (0.9) 1.0 each. (c) The biased selection is caught at the 4th event of the reference's own host run of `ol1_wa`. An engine's run has its own stream. (d) The reference's parser refuses all ten registered defects (nine at parse; amendment 4's under `multinomial_less_one`) |
| OL1-5 | The ledgers for reactions | `ledger.py`. The trace replays to the counts at every row, in exact integers. The engine's Q and W are re-booked from the trace: heat q = ln a(drawn) − ln a(reverse at the new state) = −ΔF + w, and reservoir work w = −Σ ν_h μ_h. Closure F(n_t) − F(n_0) = W_t − Q_t is required at every row, within a derived bound (the docstring) | On the reference's own host run of the registered ledger run (2,000 events, rows every 100; an engine's run has its own stream), the honest closure is 7·10⁻¹³. A heat sign error is caught at row 1 (closure −95). Dropped reservoir work is caught at row 1 (+9.7) |
| OL1-6 | Streams, replay and branching | `streams.py`. A repeat under the same identity must be bitwise equal in every array. A run under another identity must share no uniform and no 50-event prefix. G1's restart and branch tests carry the rest | A reused key is caught |

**Row 4b's design, in numbers.** The registered ladder's null means of n_T at the four times:
- rung 5: 1.484, 2.163, 2.711, 2.959 (standard deviations 0.88–0.90);
- rung 320: 100.88, 144.57, 178.62, 193.02 (about 7.0).

`mass_action.design_numbers` recomputes every one, with the powers, from the registered files.

## Roles and records

The harness reads only saved bundles and the engine's FORMAT.md, never engine source. The names
below are the references' canonical names. `engine_layout.py` is written once the family's FORMAT.md
exists, and maps its names onto these. Each role is needed under both probed convention pairs unless
marked.

| Role | Content | Rows |
| --- | --- | --- |
| `kernel_probe` | Over `ol1_wa` at the registered states: `input_states` [S, D] (the echo, compared bitwise), `a_plus` and `a_minus` [S, R] for every step, the declared tokens, and step and place order | 1, 4a |
| `boundary_probe` (amendment) | The same arrays over `ol1_boundary` at its six registered states (`designs/ol1_boundary_probe_states.json`) | 1 |
| `closed_world`, `closed_world_uncatalysed` | The same arrays over every state of `ol1_wa_closed` and of its uncatalysed variant | 2, 3a |
| `refusals` | For each `designs/refusals/*.world.json`: refused (true/false) and the message. Needed once | 4d |
| `wb_ensemble` | Per rung: `observation_counts` [runs, 4, D] at the registered times, and each run's stream identity (all distinct). Needed once; the pool takes no token | 4b |
| `ledger_run` | `ol1_wa` from its initial state to 2,000 events, diagnostic. It holds `event_time`, `event_channel` and `event_uniforms` [E, 2]; `row_event`, `counts` [rows, D], `heat_kT` and `work_kT`, rows every 100 events and the last; and in run.json the tokens, the SSA convention (`tau`, `select`), the channel table (step, direction, code, in fold order), the stream identity, and (amendment 4) the `end_reason`, which must be `max_events` | 4c, 4d, 5 |
| `replay`, `other_stream` | `ledger_run` repeated under its identity, and under another identity | 6 |
| `rescale_pair` | `ol1_wa_closed` and `ol1_wa_closed_x2` under one stream identity, 500 events each: `event_time` and `event_channel` | 3b |

**The harness** (`python -m validation.ool.references.harness`):
- `make-probes OUT_DIR` writes the registered inputs: the probe states, the closed-world states, and
  copies of the design and world files;
- `run --roles ROLES.json` runs the rows.

**Exit status:** 0 when every requested row passes; 1 when a check fails; 2 when a record, role or
declared token is missing or malformed.

`standin.py` writes a complete stand-in record set from the host oracle for dry runs. On it every
row passes.

## Amendments

**17 November 2026, after the registering commit 08870ef6 and before any engine output.**
Amendments 1–3 follow from a review of the registered design; amendments 4 and 5 (the latter on 18
November) follow the lead's rulings.

1. **The extinct rule is now probed in the forward direction.**
   - `ol1_wa` reaches the extinct boundary only through the reverse of a join, while §0.2a rules both
     directions.
   - The new world `ol1_boundary` has a membrane of A only, with A and D held in the pool. Its steps
     are a join x1, a declared leave x3 (A@membrane → A@pool) and a two-molecule leave x4
     (2 A@membrane → D@pool).
   - It is probed at A = 0..5 under the role `boundary_probe`, in row OL1-1.
   - Kolmogorov's check now also closes anti-parallel two-cycles: a step and a step declared in the
     opposite direction, here x1 and x3.
   - Under `extinct`, the forward x3 at A = 1 fires at k and x4 at A = 2 at 2k: the cancelled forms
     1/ff(0, 0) and ff(2, 2)/ff(1, 1). A literal zero there fails the row.
2. **The harness enforces the registered sizes.**
   - The ladder must have 2,000 runs per rung at the four times; otherwise the record is refused
     (status 2). A smaller ensemble would otherwise be judged at a power the design never
     registered.
   - The rescale pair must have 500 events per run, as the ledger run must have its 2,000.

3. **The harness enforces the probed pairs and the ledger's rows** (after d17e05c9, before any engine
   output).
   - Every per-pair role (the probes, the ledger run, its replay and the other stream) must hold
     exactly the two probed convention pairs, once each.
   - The ledger run must save the registered rows: every 100 events, and the last.
   - Otherwise the record is refused (status 2). One pair alone, or a run that saves row 0 only,
     would pass vacuously.

4. **Amendment 4: the lead's rulings of the same evening** (after 2d69c118, the merge of main
   d3d58d8e; before any engine output).
   - **(a) The empty common state** (§0.2a, as amended).
     - Wherever the membrane factor E(m)/ff(N − c, r) is 0/0, the cancelled form 1/ff(N − 1, r − 1)
       applies, under every `last_molecule` token. That happens when a step's common state has an
       empty membrane while neither end state does: a lone molecule changing form, or two joining.
     - `kept` gives rate zero only to a pair one of whose end states has an empty membrane.
       (Amendment 5 rewords this to the lead's ruling: only for a pair whose step changes the
       membrane's count.)
     - The values, derived from the reference's own F and rules, with k each step's forward
       constant:
       - r3 at a lone A fires at k under every token pair.
       - r1 at one A and one B fires at k/2 under `multinomial` and at k under
         `multinomial_less_one`.
       - r2 at two A fires at k under `multinomial` and at 2k under `multinomial_less_one`.
       - Each reverse is positive and equals a⁺·e^{ΔF−w} exactly. Detailed balance holds there
         as for every other pair.
     - The kernel probe gains each membrane step's reactant-only and product-only states. Two of
       them are r1's (one A and one B) and r4's (one each of A, B and E); the third is
       (C, E) = (1, 1). The probe now has 592 states.
     - In the reference, every square and two-cycle on it still closes exactly, under all four
       pairs. Wherever the forward rate is finite and positive, the reverse equals the F path
       exactly (the design-time evidence: `evidence/amendment4.*`).
     - **Row OL1-1's registered magnitudes,** re-derived on the amended law and the 592-state
       probe (`evidence/planted_a4.*`): the identity residual of the own-state factor is now 1.39,
       and the forward form's for the N^r normaliser is now 1.5. The other magnitudes are
       unchanged.
     - **Planted:** an engine that reports zero instead of +∞ at the two singular entries. Only the
       pattern check sees it, because cycles and edges with a singular rate are skipped:
       `compare_rates` fails with one singular-pattern mismatch forward and one reverse, under
       both `multinomial_less_one` pairs.
     - **Planted:** the superseded reading, rate 0 wherever the common state's membrane is empty
       (`empty_m_zero`). The forward-form check (row OL1-4a, on the kernel probe) catches it by its
       zero pattern: at 3 entries under each probed pair, where the reference gives rates of at
       least 0.5 s⁻¹. The mismatch is categorical (zero against a positive rate), so it needs no
       tolerance. The identity check fails as well, and under `extinct` the reverse rates differ at
       5 entries.
   - **(b) The singular rate** (§0.2b rule 8).
     - r4 (A + B + E → C + E) has E@membrane on both sides. Under `multinomial_less_one` it is
       +∞ at N = r: forward at (A, B, E) = (1, 1, 1), and reverse at (C, E) = (1, 1). Both are now
       registered probe states, where the expectation is +∞; `compare_rates` checks the singular
       pattern.
     - Every world holding r4 declares `world_role: probe` (an optional key; `probe` is its only
       value), with its reason in the world file:
       - `ol1_wa` is the kernel-probe world, and its probe holds both singular states. Its
         registered runs start at N = 12 and grow (supersaturated in A). A run that reached N = 3
         with only A, B and E would stop `stalled`.
       - In `ol1_wa_closed`, `ol1_wa_closed_uncatalysed` and `ol1_wa_closed_x2`, the conserved
         moieties keep N ≥ 5 > r = 3 in all 387 states, so the singular rate never arises. The
         role is declared because the step is.
     - A tenth refusal, `refuse_singular_step_without_probe_role`, is `ol1_wa` without the role.
       It is refused when parsed under `multinomial_less_one` (its file says so in
       `refused_under`) and is an ordinary world under `multinomial`.
   - **(c) Run ends.** Every run declares an `end_reason`; one that declares none is refused
     (status 2). A registered run must end at `max_events`. A run that ends `stalled`, or ends
     any other way, fails its row (OL1-3, OL1-4c, OL1-5 and OL1-6). There is a planted test, and
     the host SSA stops `stalled` at r4's singular state.
   - **A clarification of the probe, unchanged since 08870ef6.** Its one- and two-molecule states
     include each dilute place alone, with the membrane empty. There a pool step's rate is the
     pool's mass action under every token (the last-molecule rules concern membrane-locus steps),
     and a join's rate is set by `last_molecule`.

5. **Amendment 5, text only** (18 November 2026, after 2128fe8c; before any engine output). The
   lead confirmed both of OL5's readings in the design note (main bbcbec69).
   - **`kept`, reworded.** It gives rate zero only to a pair whose step changes the membrane's count
     and one of whose end states has an empty membrane. A step in which the membrane takes no part
     fires at its own rate under every token. A pool step at a probe state with an empty membrane
     fires at the pool's mass action. Amendment 4's wording, read literally, also zeroed those pool
     steps. The reference never did: its `kept` acted on membrane-locus steps only.
   - **Rule 8's condition, cited.** "A membrane place on both sides" means one and the same
     membrane species among both the step's reactants and its products, as E is in
     A + B + E → C + E. A step whose membrane species differ between its sides meets §0.2a's 0/0
     at N = r and takes the cancelled form. That is how amendment 4 read it.
   - **What changed:**
     - the token meanings in `ol1_conventions.json` and the amendment record in
       `ol1_design.json` (text);
     - the law and the float path now state the count condition explicitly.
   - **No registered input changed.** The worlds, the probe states and the planted controls'
     numbers are as at 2128fe8c. Every expected value is bitwise unchanged on every registered
     probe, under all four token pairs (`evidence/amendment5_*`).
   - **The pool-step case gets a planted test but no registered number.** It is an engine that
     freezes every channel at an empty membrane under `kept`. The forward-form check's zero
     pattern catches it at the probe's empty-membrane states that hold pool molecules
     (`test_ool_references_laws.py`).

**The same day, on the stand-in only (not the design).** Honest stand-in probes are now
evaluated by the float path (`FloatRates`), as a float64 engine would report them. A test holds
that such a kernel passes the registered tolerances: Kolmogorov below 10⁻¹³ against a tolerance
near 10⁻¹². So the tolerances have now met a float kernel, not only tables rounded from the exact
law.

## Then OL2–OL4, in order (D212's priority)

The programme's first target is the user's (D212): a first-principles physical simulation of lipid
assemblies, with lipids and chemicals going in and out, and fission. So OL2's and OL3's references
put first the claims that target rests on: exchange equilibria and their rates, geometry from the
counts, and division's partition and work. Each is registered here before its engine output exists,
in the same form as OL1.

1. **OL2: exchange equilibria and rates (first).**
   - **Equilibria.** The CAC as F's closed form, c_cac = c0 exp(μ°_bil − μ°_sol), for one
     amphiphile with a size-independent geometric term. The multicomponent threshold Σ K_i ρ_i = 1.
     The exact equilibrium size distribution of a closed world (one or two assemblies and a finite
     pool), by enumeration. Planted: the finite-size term's sign.
   - **Rates.** The deterministic relaxation of one assembly in a finite pool has closed forms: with
     insertion ∝ N it is logistic. The exact master-equation means are the null. Planted: a wrong
     encounter exponent (N against N^{1/2}).
2. **OL2: geometry from the counts.**
   - **The quantities.** A = Σ n_i a_L,i/2, V_osm = N_imp/c_ext, V_sph = A^{3/2}/(6√π),
     V = min(V_osm, V_sph), v, and σ = ΔpR/2, all at registered states.
   - **Tension-driven exchange.** The zero-tension end state and the two-vesicle equilibrium split,
     in closed form; an amphiphile's potential falls by σa_L/2. Planted: a_L off by a factor of two;
     a wrong Laplace factor; a wrong V_sph constant.
3. **OL2: the finite shared pool.** The exactness of two-level selection, by the oracle under the
   declared convention. The stationary law of a shared-pool closed world.
4. **OL3: division's partition and work.**
   - **Admission.** The thresholds v ≤ k^{−1/2} (0.707, 0.577 and 0.5).
   - **The partition.** The membrane's split at given daughter areas is multivariate hypergeometric
     for equal areas per molecule. Unequal areas need a declared rule, which is a question for the
     lead. The lumen's split is multinomial by volume. Enumeration at small N, and a χ² test with
     registered power at large N.
   - **Work.** The split's ΔF is booked as shear work, with daughters' areas summing to the
     parent's; serial transfer's sampling law.
   - **Planted:** a split at 0.55; areas that do not sum; an admission threshold off; a binomial
     split presented as hypergeometric.
5. **OL4: energy.**
   - **Ledgers and moieties.** Ledgers with stored energy, reservoir and schedule work; moiety
     ledgers.
   - **A driven cycle.** A fuel-to-waste cycle's steady flux by Hill's diagram method (exact), and
     its entropy production.
   - **Refusals.** Unsourced driven laws are refused, as registered refusals.
   - **Planted:** a fuel step booked without its stored term; a driven law admitted.

### Built ahead of the rulings (17 November 2026)

These pieces need no ruling, so they are written and tested now. The lead rules OL2's and OL3's
open choices as §0.2b of the design note before OL2 starts. They were sent as seven questions:
- the exchange encounter;
- the lumen's evaluation state;
- lysis;
- the geometric term at small N;
- the two-level fold;
- permeation;
- the unequal-area partition.

The worlds, token menus and probe files of OL2 and OL3 are registered after §0.2b, before any
OL2 engine output.

- **`geometry.py`** (OL2: geometry from the counts):
  - A, V_osm, V_sph, V = min(V_osm, V_sph), v, R, Δp and σ = ΔpR/2, at registered states of a
    100 nm oleate-like vesicle (a_L = 0.3 nm²; c_ext = 0.2 M; osmotic excess 0.8, 1.0 and 1.2);
  - the potential drop σa_L/2 equals −∂F_lumen/∂n on both sides of the floppy–tense boundary,
    where F is continuously differentiable;
  - the zero-tension area (6√π V_osm)^{2/3};
  - the two-vesicle end state at equal tensions, with the degenerate both-relaxed case reported;
  - the admission thresholds k^{−1/2}.
  - Planted: a_L doubled, the Laplace factor doubled, 6π for 6√π.
- **`division.py`** (OL3: the equal-area partition):
  - the multivariate hypergeometric membrane split for k daughters of fixed counts, equal to
    brute-force labelled counting;
  - the multinomial lumen split by V_j/V;
  - count conservation;
  - a registered χ² design: parent (40, 30, 10), 400 splits, eleven pooled cells, α = 10⁻³. Its
    power against a split at 0.55 is 1.0, and against a binomial split presented as
    hypergeometric it exceeds 0.999.
- Tests: `test_ool_references_geometry.py` and `test_ool_references_division.py`.

## OL2 and OL3, registered 18 November 2026

**Registered before any OL2 or OL3 engine output exists**, under the design note's §0.2b, §0.2c
(rule 4 as corrected on 18 November: A = q·W/2, with W counting the footprints in quanta) and §0.2d
(the lead's rulings on my questions, at 7fb8816f on `ol-rulings-20261118`, with item 6 confirmed
and extended and item 9 added at 95c98b5a), with §2.5, §3, §4 and §5.2. This supersedes the plan
above for OL2 and OL3. Nothing here reads `src/cells/`, the builder's branches or worktrees, the
OL2/OL3 design check note, or any engine output beyond OL1's probe folders used for OL1's verdicts.

**Modules.**
- `ol2.py`: the law in integer quanta. W = Σ n_i k_i, A = qW/2, R, V_osm over every lumen species
  with c_ext held, V_sph converted to L before the minimum, the reduced volume, σ = ΔpR/2 on the
  tense branch only; F with the lumen's term (§0.2d 3) and C_close = 8πκ + 4πκ̄ per vesicle; joins
  under both encounter tokens and entries under `permeation_area`, a⁺ = k·E(m)·ρ0·θ⁺ (§0.2d 2 and
  4); count_on_m for membrane steps; first-order pool steps; every reverse from the exact ΔF,
  computed incrementally so that it is precise although |F| reaches 9×10⁵ k_BT; the floor on the
  end states of area-changing pairs (§0.2c rule 5); lysis on the end state (strict), its release and
  its one-row booking (§0.2d 7); the shear work.
- `population.py`: the world model with its draw addresses (domains 1, 2, 5 and 6), the two-level
  map with its guard (§0.2d 5), the clock rule (§0.2d 6, ruled, extended to a single lineage's own
  counter at 95c98b5a), shear at declared times or Poisson gaps, admission v ≤ k^(−1/2), C3x and
  the lumen split from each attempt's block (`partition.py`), the floor's refusal, birth lysis,
  slots, `slots_full`, serial transfer (one draw per living assembly, the K_keep smallest kept,
  ties by slot) and its booking (§3.1–§3.3), and the replay that reruns all of it on a trace's own
  uniforms; the stream, closure and environment checks.
- `ol2_checks.py` (kernel tables and stationary laws), `ol3_checks.py` (the partition probe),
  `registered2.py` (the inputs), `refusals2.py` (22 declarations and the references' parser),
  `harness2.py` (the rows, with the canonical record layout in its docstring), `standin2.py`,
  `design2.py` (the design file, `designs/ol2_ol3_design.json`).

**Inputs** (`designs/`): ten worlds (`*.world2.json`), six runs (`ol2_*_run.json`,
`ol3_*_run.json`), four probe-state files (696 states for each kernel world; 61 one-vesicle
states for `ol2_closed`; 12,432 for `ol2_two`'s 6,216 closed-world states), six partition parents
(`ol3_parents.json`, 4,000 attempts each; N mod k ≠ 0 at k = 2 and 3 with equal and unequal areas,
and one N mod k = 0 case), and 22 refusal declarations (`refusals2/`). Every value is a declared
test parameter, unsourced.

| Row | Claim | Records | Planted controls caught (margin) |
| --- | --- | --- | --- |
| OL2-1 | Cycle closure; a⁻/a⁺ = e^(ΔF − w) with the lumen's F; the forward forms under both tokens, the floor's zero pattern and the lysis flags; the geometry | Kernel probes of `ol2_wa` and `ol2_wa_diffusion` | Extent on the target state (forward, 10⁻³ against 10⁻¹²); a radius for an area (17.2); a dropped c0 (6.91); no lumen term (identity 72.8 against 10⁻⁸); the lumen's sign (146); the reverse's sign (167); the floor on every step (53 zero-pattern entries); a_L doubled; the Laplace factor (1,852 lysis flags; σ off by 0.55); 6π for 6√π (identity 40.7); V_sph in m³ (V_sph off by 0.999); impermeants only in N_L (identity 6.7) |
| OL2-2 | Closed worlds relax to exp(−F)/Z: one vesicle across its kink; two vesicles sharing a pool (the swollen one takes amphiphiles) | One-vesicle probes of `ol2_closed`, `ol2_two` | Total variation 0.070 to 1.0 against a tolerance of 10⁻⁷ (honest 1.3×10⁻¹¹ and 1.6×10⁻¹¹) |
| OL2-3 | Lysis fires on the end state, releases monomers to their pool places and the closure cost, books one row, ends `lysed` | Run `ol2_lysis_run` | Closure kept (heat off by C_close = 125.7 k_BT; the ledger does not close); release work omitted (heat and reservoir work) |
| OL2-4 | The two-level map with the pool's group and empty slots; no discards without a schedule; closure | Run `ol2_shared_run` | A flat one-level map (channel choices) |
| OL2-5 | Every registered declaration refused | Refusals | Any one accepted |
| OL3-1 | C3x and the lumen split, replayed from each attempt's block and against their exact laws | Partition probe | G1's sizes, no π, the lumen by area or by equal shares: family power 1.0 at M = 4,000; the largest minimiser by replay |
| OL3-2 | Poisson shear and serial transfer: the clock rule, the schedule streams, the transfer's sample, slots and booking, closure | Run `ol3_population_run` | The counter not advanced, a crossing draw fired, the K_keep largest kept, no draws when all are kept, gaps −ln(1 − u)/λ, admission at 1/k, the floor on the parent, the highest free slots, the fresh pool's F to the sink (sink −37.1 against −1,259.4 k_BT), the old pool not sunk (closure off by 4.45×10³), the closure cost added again |
| OL3-3 | Declared shear times: admission, C3x at k = 3 with N mod 3 ≠ 0, the floor's refusal, birth lysis, the shear work | Run `ol3_shear_probe_run` | A daughter beyond σ_max kept alive; the floor on the parent; the highest free slots; (k − 1)·C_close added again; the closure cost kept at a birth lysis |
| OL3-4 | A single lineage with a schedule: the clock rule on its own counter, the unfollowed daughters' sink | Run `ol3_lineage_run` | The counter not advanced; a crossing draw fired; admission at 1/k |
| OL3-5 | A full set of slots stops the run `slots_full` before the split | Run `ol3_slots_full_run` | Admission at 1/k |

Every run row also checks the environment record's threefry flag (§0.2d 9) and the run's end
reason, and needs its run to exercise what the row tests (for example a birth lysis, a transfer
that keeps all, a discarded draw). A run that does not is inconclusive (exit 2), not passed. Over
200 stand-in seeds per run, every requirement was met in all 200 for each of the six runs. A birth-lysis parent
has a daughter beyond σ_max with probability 0.90 (Monte Carlo, 200,000 splits), so all eight
parents miss with probability 10⁻⁸.

**Zero-power entries and readings.** The design file lists the zero-power entries and the
readings. The seven readings that bind a replay were ruled as §0.2d item 10 on the same day
(amendment 6, below).

**Use.** `python -m validation.ool.references.harness2 --records DIR --out verdict.json` runs the
rows on records in the canonical layout, which an adapter writes from the engine's bundles once the
family's format exists. The run rows need diagnostic records: every draw of domains 1, 2, 5 and 6
with its address, uniforms and fate (discarded draws, the draw that ends the run and a Poisson gap
past t_end included), the channel table (its fold orders), and each event's changes and ledger
terms. The replay takes the carrier keys from the trace and checks that the trace is the registered
run (mode, slots, t_end, schedules, the founders' counts and the pool), with exit 2 if not. `python -m validation.ool.references.standin2 --out DIR` writes honest stand-in records,
and `--planted FORM` (or `--law-planted`, `--partition-planted`) a planted set.

Tests: `test_ool_references_ol2.py` (the registration, the geometry, the encounter rates, the floor,
the incremental ΔF, the kernel and stationary checks with every planted law, lysis's booking) and
`test_ool_references_ol3.py` (the two-level map, the clock rule, Poisson gaps and the transfer,
the bookings, each planted run behaviour by its row, the partition probe, and the harness end to
end: exit 0 honest, 1 planted or a refusal accepted, 2 a missing manifest). Evidence:
`/mnt/workspaces/Cells/ool-references-20261117/evidence/` (`ol2_ol3_margins.*`,
`ol2_ol3_coverage.*`, `ol3_birth_lysis.*`).

### Amendment 6 (18 November 2026): §0.2d item 10, the replay conventions

The lead ruled my seven replay readings as §0.2d item 10 (c8b22371 on `ol-rulings-20261118`),
after the builder confirmed them against its design and made them more precise. This is still
before any OL2 or OL3 engine output. No registered input changes: the worlds, runs, probe states,
parents and refusals are the same files. The references now follow item 10's wording:
- **The followed daughter.** Every single-lineage split must record the daughter it follows (G1's
  `fission_followed`, generalised to k). A missing, out-of-range or non-integer field is a record
  error (exit 2). The replay never assumes daughter 0.
- **Counters.** Every counter starts at 0: domain 5, domain 1 at each assembly's birth, domain 2
  and domain 6. A new lineage key's first counter is no longer read from the record. The keys
  themselves still come from the record (the relations rule, via the `lives` table).
- **Birth lysis.** Every daughter takes its slot before any birth lysis, which then frees it. A
  birth-lysed daughter's slot is recorded and compared. This moves the daughters' slots at the
  k = 2 shear of `ol3_shear_probe_run`'s reference trace, and nothing else.
- **Simultaneous events and t_end.** A scheduled event due now applies before any draw. So two
  events at one time take no draw between them, and apply in schedule-index order, each to the
  assemblies alive at its own start. A declared time equal to t_end applies; a later one never
  does. Neither case occurs in a registered run: every run's reference draws, schedule draws and
  events are unchanged (checked against the traces before the amendment).
- **Channel order.** A single lineage's channel table must be the ruled order too: the declared
  steps forward, then the same steps reverse.
- **Every recorded draw.** Every recorded draw must be one the reference makes. The exemptions for
  a gap past t_end and for a block recorded at a `slots_full` stop are gone, since the ruled order
  tests the slots before the draw.

Tests added to `test_ool_references_ol3.py`: the followed daughter is required; a new key starting
at 1 fails; birth-lysed daughters take a slot and free it; simultaneous schedules take no draw
between them; a time at t_end applies and a later one does not. The lineage-order test now expects
a permuted order to fail.

## What could not be confirmed from the sources

- **The design's §2.2 table writes F in the continuum (Stirling) form.** Textbook mass action
  (§2.1) and E1's exact product form need the discrete ln n! form, which the family adopted (§0.2a).
  The references refuse `continuum` for the exact kernel.
- **E1's kinetic split is not stated in the design.** Of four natural splits, only forward
  constants 1 with reverse constants 1/K reproduce its 0.0829822. A non-reversible law's stationary
  law depends on the split.
- **E2's per-contact interaction ω^{n₁n₂} is not §2.2's regular mixing (1/2N)Σχnn.** So E2 tests
  the enumerator only. `ol1_wa_closed` carries the engine-facing regular-mixing check.
- **A membrane split at fixed daughter areas with unequal areas per molecule (OL3) does not fix
  the daughters' counts.** Its law needs a declared rule, which goes to the lead before OL3's
  registration.
