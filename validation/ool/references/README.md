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
  - `designs/ol1_kernel_probe_states.json` (589 states of `ol1_wa`);
  - `designs/ol1_closed_world_states.json` (387 states of `ol1_wa_closed`).
- The design file, `designs/ol1_design.json`, and the reference modules.

The registering commit is 08870ef6. The tests, the harness and the stand-in followed on this branch
the same day:

| Test file | What it holds | Planted controls |
| --- | --- | --- |
| `test_ool_references_registration.py` | Every committed design file equals its generator; every world parses; every registered refusal is refused; the menu refuses missing, unknown and refused tokens | A changed byte; a float that is not its exact value; each registered defect |
| `test_ool_references_laws.py` | Exact Kolmogorov, the products' rule against F, and the edge identity, on a slice of the probe under all four token pairs; the extinct boundary's k⁻; the float rates against the exact law; E1 and E2 | Every row OL1-1 and OL1-4a form, each by its named check, under both probed pairs |
| `test_ool_references_closed_world.py` | 1,312 exact edges; stationary laws within 10⁻¹³; catalysts that leave the law unchanged | Five planted laws and the other measure depart; a rate leading outside is caught |
| `test_ool_references_mass_action.py` | The Riccati form against SciPy's Radau; the master equation's O(1/X) approach; the registered null means and powers; the test on exact samples | Wrong sign, S → T, and biased selection fail; an underpowered design is refused |
| `test_ool_references_runs.py` | Replay, ledger closure, moieties, the bitwise time rescaling, and streams on host runs | Biased selection, a heat sign error, dropped work, an update off by one, a forward-only factor, a reused key |
| `test_ool_references_harness.py` | Every row passes end to end on the stand-in (exit 0) | A planted form fails its row (exit 1); a missing role, manifest or token, or a changed echo, exits 2 |

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
  both measures. `laws.py` derives it, and `exact_wa` checks it exactly on all 4,123 probe
  state-step pairs.
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
| `last_molecule` | `kept`, `reversible` (with c = 0), `extinct` (with c = 1) | `extinct`: a channel whose result empties the membrane fires at the pair rule's cancelled form, E(m)/ff(N − 1, r) → 1/ff(N − 1, r − 1), in either direction. It is one-way, and its heat is booked against F_mem(empty) = 0 |

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
| OL1-1 | Every channel keeps local detailed balance | `detailed_balance.py`, `laws.py`. On the engine's kernel table at 589 registered states of `ol1_wa` (seed 2026111701; 24 base states with counts at most 9, every square's corners, and boundary states), three checks run. (1) Kolmogorov's criterion on 360 squares and 133 parallel two-cycles. It needs no convention and cannot be met by comparing the engine with itself. (2) The identity ln a⁻(n′) − ln a⁺(n) = F(n′) − F(n) − w under the declared tokens. (3) The reverse rates, the extinct boundary's cancelled form included. The tolerance is 64u(8 + Σ\|ln a\|) per cycle, below 3·10⁻¹² here. In the reference itself every square and two-cycle closes exactly (RatExp), under all four token pairs | Under (multinomial, kept): the factor at each direction's own state fails Kolmogorov (max 0.0074, 124 cycles) and the identity (0.125). Catalysis on the forward channel only fails Kolmogorov (0.057). A one-sided off rate (r3's reverse × e^{x_D}) fails Kolmogorov (0.061). A wrong sign of ΔF fails the identity (10.6). A dropped c0 fails the identity (6.91). The other measure fails the identity (0.693). A wrong last-molecule token fails the boundary rates. The honest table's largest residual is 2.7·10⁻¹⁵ |
| OL1-2 | A closed world relaxes to exp(−F/k_BT) | `closed_world.py`. In the reference, a⁺(n)w(n) = a⁻(n′)w(n′)e^{w} holds exactly on every edge of `ol1_wa_closed` (1,312 edges, all four token pairs). The world is connected, so π = w/Z is its unique stationary law. On the engine's table, the generator's stationary law (sparse LU) must lie within total variation 10⁻¹⁰ of exp(−F)/Z, and Kolmogorov must hold on all 1,821 squares and 243 two-cycles | The planted stationary laws depart: own-state factor TV 0.083; forward-only catalysis 0.30; one-sided off rate 0.0079; dropped c0 0.997; wrong sign 0.997; the other measure 0.035. Honest: 5·10⁻¹⁶. **The design's probes reproduce exactly.** E1 gives TV 0.0829822 with cycle ratio 143/128. The kinetic split (forward constants 1, reverse 1/K) is identified by reproduction: reverse constants 1 with forward K give 0.0842. E2 gives TV 0.5407884 with ratio 2/3; its per-contact ω is not §2.2's form, so it tests the enumerator only |
| OL1-3 | Catalysis is kinetic only | `catalysis.py`. (3a) The closed world with its catalysts and without them must both relax to exp(−F)/Z. (3b) The closed world and its rate-doubled variant, under one stream identity, must fire the identical channel sequence (500 events) at exactly half the times. Doubling is exact in floating point, so the comparison is bitwise | (3a) Forward-only catalysis departs (TV 0.30). (3b) A factor on forward channels only changes the sequence |
| OL1-4 | Mass action with registry potentials | `laws.py`, `mass_action.py`, `ssa_oracle.py`, `world.py`, in four parts. (a) The forward form, on the kernel probe, under the declared tokens. (b) The large-system ladder on `ol1_wb_m{5,20,80,320}`: 2,000 runs per rung to 2 s, means at 0.25, 0.5, 1 and 2 s. Each mean is z-tested against the **exact master-equation mean** of its rung, Bonferroni over 16 tests (z = 4.003). The ODE is not the null, because the exact mean differs from it by O(1/X). The ODE's closed form (Riccati) and SciPy's Radau agree to 2.5·10⁻¹⁴. The gap falls fourfold per rung: −0.0188, −0.0046, −0.00114, −0.000285 at t = 0.25 s. (c) The host oracle replays a diagnostic run under common variates. (d) Every registered refusal is refused at parse, and every moiety is conserved at every row | (a) n^α for the falling factorial (0.693), N^r for the draw's normaliser (0.186), the extent without its offset (0.693; an error under c = 0 only, since under c = 1 it is the rule) and a dropped c0 (6.91) each fail the forward form. (b) Family power at 2,000 runs: n² for n(n−1) 0.998; dropped c0, wrong sign, S → T run for 2 S → T, and selection biased against reverse channels (0.9) 1.0 each. (c) The biased selection is caught at the 4th event of the registered run. (d) The reference's parser refuses all nine registered defects |
| OL1-5 | The ledgers for reactions | `ledger.py`. The trace replays to the counts at every row, in exact integers. The engine's Q and W are re-booked from the trace: heat q = ln a(drawn) − ln a(reverse at the new state) = −ΔF + w, and reservoir work w = −Σ ν_h μ_h. Closure F(n_t) − F(n_0) = W_t − Q_t is required at every row, within a derived bound (the docstring) | On the registered run (2,000 events, rows every 100) the honest closure is 7·10⁻¹³. A heat sign error is caught at row 1 (closure −95). Dropped reservoir work is caught at row 1 (+9.7) |
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
| `closed_world`, `closed_world_uncatalysed` | The same arrays over every state of `ol1_wa_closed` and of its uncatalysed variant | 2, 3a |
| `refusals` | For each `designs/refusals/*.world.json`: refused (true/false) and the message. Needed once | 4d |
| `wb_ensemble` | Per rung: `observation_counts` [runs, 4, D] at the registered times, and each run's stream identity (all distinct). Needed once; the pool takes no token | 4b |
| `ledger_run` | `ol1_wa` from its initial state to 2,000 events, diagnostic. It holds `event_time`, `event_channel` and `event_uniforms` [E, 2]; `row_event`, `counts` [rows, D], `heat_kT` and `work_kT`, rows every 100 events and the last; and in run.json the tokens, the SSA convention (`tau`, `select`), the channel table (step, direction, code, in fold order) and the stream identity | 4c, 4d, 5 |
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
