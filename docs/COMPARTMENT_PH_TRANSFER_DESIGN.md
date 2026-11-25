# Compartment pH and state-conditioned transfer: FR-4 and FR-5 (design)

> **Legacy cleanup (25 November 2026, D386).** Paths under `src/cells/legacy/` and the older model
> IDs named below left the engine. The tag `pre-cleanup-2026-11-25` keeps them.

**Status (16 November 2026).** Written 15 November 2026 by the FR-4/FR-5 physics owner (D176), as
design before code (D142).
- **FR-4 is built and on main,** with D172's round (ab267c39, tag `d172-landed-2026-11-16`):
  - its kinds, `cells.rapid_proton_buffer@1`, `cells.transporter@1` and `cells.passive_routes@1`;
  - FR-1's refusal 4, version 1.1;
  - its world and qualification tools (`validation/compartment_ph_engine/`,
    `validation/tissue/compartment_ph_*.py`).

  Its protocol, `fr4-acidification-v1`, is registered and judged on 17 November 2026: passed, 21 of 21 judged criteria (D195; tag fr4-v1-qualified-2026-11-17). Its dt study's development reading passed on
  16 November. Registration is the lead's.
- **FR-5 (§16) is accepted,** and built and on main since fr45-next merged (16 November), for
  development, not judged. Its protocol, `fr5-transfer-v1`, is registered and judged on 17 November 2026: passed, 51 of 51 judged criteria (D195; tag fr5-v1-qualified-2026-11-17). What merged:
  - the two source kinds;
  - refusal 4 version 1.2 and refusal 5 version 1.1 (CLOSED_COMPARTMENT_DESIGN §3.4.2–3.4.3);
  - FR-5's start part.

  The routing door and the kind schedules it uses are the core's (INNER_MODEL_V4_DESIGN §7.4 (l),
  (n)).
- **Finite fuel (§17) is accepted,** ruled by the lead on 16 November. It is built after FR-5's
  dt study is launched.
- **Its first readers:**
  - the references agent, who writes independent references from Appendix A without reading
    engine code;
  - the core and integration owners, whose interfaces it names.
- **Not here:** engine code, and any study's names. Acceptance worlds are generic (D176).
- **Builds on:**
  - [ARCHITECTURE.md](ARCHITECTURE.md), "The modular core";
  - [INNER_MODEL_V4_DESIGN.md](INNER_MODEL_V4_DESIGN.md) (§10 fuel, §13.3–13.4, §15.4);
  - [CLOSED_COMPARTMENT_DESIGN.md](CLOSED_COMPARTMENT_DESIGN.md) (FR-1: §1.3 lumping, §3.1–3.4 the
    compartment's capacitor and the charged door);
  - [SCOPED_COMPOSITION_DESIGN.md](SCOPED_COMPOSITION_DESIGN.md) (door S, §6);
  - [SHARED_INVENTORY_REACTIONS_DESIGN.md](SHARED_INVENTORY_REACTIONS_DESIGN.md) (D152);
  - [FEATURE_REQUESTS.md](FEATURE_REQUESTS.md) FR-4 and FR-5.
- **Evidence:** `/mnt/workspaces/Cells/d172-restructure-20261115-01/fr45/charged_patch/`
  (criterion, probe, results). **S** marks our own arithmetic or inference.

## 0. The decisions, in plain terms

1. **Protons are one +1 species row.** At a buffered node the row holds the node's titratable
   proton content (free plus bound, "proton equivalents"). Free H⁺ is algebraic state, computed by
   the node's buffer closure at every stage, and every law reads it from there.
2. **Buffering is a rapid-buffer closure, not kinetic reactions** (§4). Its pK comes from the
   registry's standard potentials. Its envelope and error budget are declared first (D175), with a
   case outside the envelope that must fail. Appendix A.2 gives the full protonation kinetics, so
   the references can show convergence to the closure.
   - Protonation relaxes at about 10⁸ s⁻¹ (**S**), so explicit kinetics are impossible.
   - A split implicit block would let the transport step move the free pool by several times its
     own size per step: a 250 nm lumen at pH 7.4 holds about 1.6 free protons (CP4).
   - The closure is the exact fast limit, conserves material and charge exactly, and is the
     organelle-pH literature's own treatment. It is declared as a reduced representation (D175).
3. **Counterions are explicit rows on explicit routes,** Cl⁻ in or K⁺ out, chosen by the world.
   Without one the pump charges the patch and stalls; that is the negative control.
4. **The charged patch needs an implicit route for a practical step** (the charged-patch test,
   §7.2–7.3).
   - **What refuses is the booking.** @3's energy ledger refuses an explicit patch at dt × G/C_b
     above about 0.05. At those refused steps the state is right (≤ 0.36% of its change, second
     order). What fails is the routes' heat quadrature, at 5–6 times the state's error.
   - **Recommended, not settled:** an exact booking with the implicit patch. The run matched
     neither reading written beforehand. The exact booking would silence today's only
     over-large-step check, so B7's constant stays open: (a) now, (b) or (c) later, in §7.2. The
     sweep shows the term refuses no existing world.
   - **With today's booking:** lysosomal Cl⁻ needs dt ≤ 0.01–0.03 ms (25–90 CPU-hours per 900 s,
     an upper bound), and FR-5's pores about 0.1–0.3 µs.
   - **The implicit patch** is designed in §7.3. It is local per compartment: a diagonal-plus-rank-one
     Newton on the compartment's amounts, with exact booking and no change to the global field
     factorization.
   - **FR-4's first world runs explicitly** with a small K⁺ conductance (5e-10 m/s at 140 mM:
     0.025 at 1 ms, carrying the pump's current at about 2 mV, **S**), with its dt declared by the
     world.
5. **Fuel is maintained under F2:** held ATP, ADP and Pi rows at the owner's cytosol, with one
   authority for their standard potentials. The scope label is "maintained fuel: no depletion".
6. **The thermodynamic boundary** (§5.2).
   - Hydrolysis is transformed at the hydrolysing node's declared reference pH and pMg.
   - That node's proton row may be dynamic, provided its pH stays within a declared band (checked,
     refused outside) and its fuel is maintained. Maintained hydrolysis is then proton-neutral.
   - Hydrolysis at a node outside its band, and finite fuel at a node with dynamic protons, are
     refused in version 1.
7. **The proton pump** is a transporter law on the bounding patch, `proton_atp_mass_action_positive@1`.
   It moves n H⁺ outward per ATP, with the Na/K pump's thermodynamically consistent form, and is
   evaluated inside the inner step (door S's stage `inner`).
8. **FR-5:**
   - Damage is FR-1's prescribed injury and resealing law on the bounding patch. It reaches the
     leak's and the transfer's rates as a control factor through the routing door (door S §6).
   - The pH condition is a second factor on the same routing door. It reads the compartment's
     free H⁺ from the closure.
   - Ion pores wait for the implicit patch. Proton and neutral leaks run explicitly.
   - The routing door's use is designed in §8: sources, sinks, `multiply`, timing and who does
     what.
   - On a lumped population, an injury is uniform over its members. One member, or a subset, is
     injured by splitting the population into two compartments (§9).
9. **The first worlds fit the species cap.** FR-4 needs 9 rows, FR-5 10, against 16.

## 1. Scope, representation and claims

- **Entity:** FR-1's owned compartment, a face-free finite node bounded by one patch whose inside is
  the owner's cytosol. Its identity comes from `compartments.identity_map`.
- **Representation, declared per world (D174, D175):**
  - continuum amounts;
  - either a single compartment, or a lumped population of N identical compartments as one node,
    with N × volume, area, capacitance and transporter capacity.
  - Lumping is exact for identical members, because V/A and C/A are kept (FR-1 §1.3). The lumped
    compartment is a deterministic continuum model, not a stochastic mean.
- **Why lumping matters here (CP4).**
  - A single 250 nm lumen holds 1.6 free protons at pH 7.4.
  - @3's absolute energy floor (2e-8 pJ) is 6% of one pump step's heat (3.2e-7 pJ at 10⁴ H⁺/s,
    1 ms, 200 mV), so the ledger cannot see a smaller error.
  - Acceptance worlds therefore use a lumped population large enough to clear the floors (§13).
  - Free protons are a continuum mean, meaningful for a population or a buffered pool, not as
    counted ions.
- **Claims kept apart (D174):**
  - numerical verification against independent references (this note's acceptance);
  - calibration;
  - a protein-free test;
  - held-out living-cell prediction.

  FR-4 and FR-5 here claim only the first.

## 2. Conventions

| Quantity | Convention |
| --- | --- |
| Units | Amount fmol; volume pL; concentration mM = fmol/pL = mol/m³; potential V; time s; molar energy J/mol; energy pJ |
| Constants | F = 96485.33212 C/mol, R = 8.314462618 J/(mol K); T declared (310 K in §13) |
| Node charge | q = F × 1e-15 × (fixed + Σ_s z_s n_s) C, with fixed the node's `fixed_charge_equivalent_fmol` |
| Patch voltage | V_b = φ_inside − φ_outside, inside the owner's cytosol and outside the lumen (@3's convention). The literature's lumen-minus-cytosol ΔΨ is −V_b |
| Face-free compartment j | V_b = −q_j / C_b exactly (FR-1 §3.1). The owner's potential is φ_i = (q_i + q_j)/C_p against a held bath through an impermeant plasma patch |
| Standard state | c° = 1000 mM (1 M) for every solute, as the pump laws' `STANDARD_STATE_mM` |
| Chemical potential | μ_s = μ°_s + RT ln(c_s/c°); electrochemical μ̃_s = μ_s + z_s F φ. Ideal dilute solutions; activity coefficients 1, a declared limit |
| pH | pH = −log₁₀(h/c°), with h the free H⁺ concentration in mM |
| Flux sign | A route's flux J is positive from the patch's inside to its outside |

## 3. Species

| Row | Valence | Meaning |
| --- | --- | --- |
| `H` | +1 | Unbuffered node: free H⁺. Buffered node: the proton equivalents H_eq = free H⁺ plus protons bound to the node's declared buffers, counted from each buffer's base form |
| Buffer totals `B_k` | z_k, the base form's valence | B_tot,k = n(HB_k) + n(B_k) at the node. Inert: no route, no reaction. The acid form has valence z_k + 1 |
| Counterions `K`, `Cl` (and `Na`) | +1, −1 | Ordinary @3 rows, moved by constant-field routes |
| `ATP`, `ADP`, `Pi` | 0 | Transformed fuel rows (F2), held at the hydrolysing node (§5) |
| Cargo `X` (FR-5) | declared (0 in §13) | Moved by the pH-conditioned transfer and the damage leak |

**Charge at a buffered node** depends on totals only (**S**). For each buffer, HB_k ⇌ H⁺ + B_k
conserves charge, so
Σ z n = n(H, free) + Σ_k [(z_k + 1) n(HB_k) + z_k n(B_k)] = H_eq + Σ_k z_k B_tot,k.
So the inner model's charge sum over the stored rows (H with +1, B_k with z_k) is exact as it
stands. No change to the field is needed.

## 4. Buffering: the rapid-buffer closure

### 4.1 The equations

For buffer k at one node, with acid dissociation constant K_k in mM:
- **K_k comes from the registry's standard potentials, never from a second parameter** (B3, one
  authority).
  - Each buffer species is declared once with the standard potentials of its two forms, μ°(B_k)
    for the base (valence z_k) and μ°(HB_k) for the acid (valence z_k + 1).
  - The proton's is μ°(H⁺), conventionally 0 at c°.
  - Then K_k = c° exp(−(μ°(H⁺) + μ°(B_k) − μ°(HB_k))/RT), with c° the registry's declared
    `standard_concentration_mM` (one authority; the worlds declare 1000), and pK_k = −log₁₀(K_k/1 M).
    pH stays defined against 1 M. The free-energy terms (§4.4) use the same declared c°. Potentials
    converted consistently to another c° give the same K; unconverted ones do not (a planted test).
  - **The closure's mask is the declared (node, row) pairs** (`buffers={cell: [B_c], lumen: [B_L]}`),
    never an amount or a per-node flag. A row that does not apply at a node is a declared trace
    (absent rows are refused): a free row at a fixed amount whose charge counts and which has no
    protonation. Adding an undeclared trace leaves h bitwise unchanged (a planted test).
  - The closure, the kinetic reference (Appendix A) and the free-energy term (§4.4) all read the
    same three potentials.
- The equilibrium is h × b_k / a_k = K_k, with a_k = [HB_k] and b_k = [B_k] in mM.
- So a_k = B̄_k h/(h + K_k), where B̄_k = B_tot,k/V.
- The free proton concentration h solves

      g(h) = h + Σ_k B̄_k h/(h + K_k) − H̄_eq = 0,   with H̄_eq = H_eq/V.

  g is strictly increasing from g(0) = −H̄_eq < 0, so the positive root is unique. One buffer has a
  closed form, written to avoid cancellation:

      h = 2 K H̄_eq / (β₁ + sqrt(β₁² + 4 K H̄_eq)) if β₁ ≥ 0, else (−β₁ + sqrt(β₁² + 4 K H̄_eq))/2,

  with β₁ = K + B̄ − H̄_eq.
- **The admissible state:** 0 < H̄_eq < ∞ and B̄_k ≥ 0. A node whose protons all sit in buffer is
  not a state: h > 0 always.
- **The buffer capacity** is β = −dH̄_eq/dpH = ln 10 × (h + Σ_k B̄_k K_k h/(h + K_k)²).

### 4.2 Why a closure, and not kinetic or implicit reactions

| Treatment | Verdict |
| --- | --- |
| Kinetic buffer reactions, explicit (D152's SSPRK(3,3), dt·L ≤ 1) | **Impossible.** Protonation is diffusion-limited, k_on of about 10¹⁰ M⁻¹ s⁻¹; at 10–50 mM of buffer the relaxation is 10⁸–5 × 10⁸ s⁻¹ (**S**), so dt ≤ 10⁻⁸ s |
| An implicit local block for the kinetic reactions, as a split part | **Not enough.** It is stable, but split from transport. @3's step moves the free H⁺ row unbuffered: the pump moves about 10 protons per 1 ms step into a 250 nm lumen holding 1.6 at pH 7.4, so the free pool changes about 6-fold within the step. The transport laws would read a wrong h within the step, and an efflux could take a trial state negative. Accuracy needs dt ≪ n_free/J, about 0.16 ms near neutral pH (**S**) |
| **The rapid-buffer closure, inside every stage** | **Chosen.** It is exact in the fast limit. Material and charge hold by construction. There is no stiffness and no splitting between buffering and transport. It is the standard treatment in organelle-pH models (Grabe and Oster 2001 and Ishida et al. 2013 carry a buffer capacity β; FR-1 §3.2 quotes both) |

The closure is a reduced representation under D175, and declares its four fields:
- **it represents** the protonation reactions HB_k ⇌ H⁺ + B_k at its node, keyed per node so that
  no second representation of them is admitted;
- **it preserves** H_eq, every B_tot,k, the node's charge and its free-energy minimum;
- **what can be asked:** free h, pH, a_k and b_k, β, and observations. Kinetic questions about the
  buffer itself are refused;
- **where it is qualified:** the envelope and budget below, declared before any comparison (D175).

**The envelope and error budget, declared before the comparison (D175).**
- **The fast rate:** each buffer's protonation relaxes at λ_k = k_on,k (h + b_k + K_k) (1/s, with
  k_on in mM⁻¹ s⁻¹). The slowest of them is λ = min_k λ_k.
- **The slow rate:** transport drives the free protons at ρ = |dH̄_eq/dt| / (β/ln 10) (1/s). That
  is the relative rate at which the equilibrium h moves, from the stage's transport.
- **The envelope, revised (state-dependent) after the FR-4 references' run 02**
  (`validation/compartment_ph/REFERENCES_USAGE.md`): the closure's estimated lag behind the kinetic
  system stays within the budget at every stage of every node the closure serves:

      |ΔpH| ≈ (ρ/λ) (β/ln 10 − h) / (h ln 10) ≤ 1e-3,   β/ln 10 − h = h Σ_k B̄_k K_k/(h + K_k)².

  - **Derivation, from A.2 to first order (S):**
    - transport moves H_eq at rate dH̄/dt;
    - the bound part's equilibrium moves at that rate times the bound share (β/ln 10 − h)/(β/ln 10);
    - the bound pool relaxes toward it at λ, so it lags by about that rate over λ;
    - the lagging protons sit in the free pool, so the error in h is that lag, and
      ΔpH = δh/(h ln 10).
    - With ρ = ln 10 |dH̄/dt|/β, this is the expression above.
  - **Why the earlier fixed ratio λ ≥ 10³ρ failed** (the references found it): it omits the
    bound-to-free factor (β/ln 10 − h)/(h ln 10).
    - That factor is about 1.5e4 at the lumen's start (pH 7.2) and about 210 at pH 5.1.
    - In §13.1's world the old ratio passes from k_on ≈ 0.83 mM⁻¹ s⁻¹, but the budget holds only
      from k_on ≈ 1.28e4.
    - At k_on = 1e3 the ratio holds by about 1.2e3, yet the lumen lags the closure by 1.26e-2 pH.
      That case is kept as a planted test (`test_planted_the_old_fixed_ratio_admits_a_case_the_lag_check_refuses`).
  - **Computable at run time,** from k_on, a parameter of the closure's own declaration (its
    stage read; D175's stand-in parameter, used only for this check and the reference, not a
    species-registry value), the stage's fluxes and the closure's state
    (`rapid_proton_buffer.lag_estimate_ph`). The run refuses a stage outside it, with the reason.
  - **No clause in dt.** The closure is evaluated exactly at every stage, so its error is this lag,
    whatever the step. A dt clause would tie a physical envelope to the numerics, and a dt study
    would move it. The step's own error is the dt study's, as for any law.
- **The error budget:** |pH_closure − pH_kinetic| ≤ 1e-3 pH units at every record time. So is the
  closure's error in H_eq-weighted fluxes, at 1e-3 relative. It is checked against Appendix A's
  kinetic reference.
- **The case outside the envelope, which must fail the budget:** FR-4's §13.1 world with the lumen
  buffer's k_on lowered to 1e-3 mM⁻¹ s⁻¹ (1 M⁻¹ s⁻¹).
  - Then λ is about 0.04 s⁻¹ (**S**, at b ≈ 38 mM). Early in the acidification, ρ is about
    0.031 s⁻¹. The pump's saturation S is about 0.276 at pH 7.2, so about 2,760 H⁺/s per member
    are pumped, or 0.07 mM/s against β ≈ 5.1 mM/pH.
  - The kinetic reference lags the closure by a large fraction of a pH unit there.
  - Both the run-time envelope check and the comparison must flag it.
- **The inside cases:** k_on of 1e10 M⁻¹ s⁻¹ (1e7 mM⁻¹ s⁻¹) and 1e8 M⁻¹ s⁻¹ (1e5 mM⁻¹ s⁻¹).
  The reference's convergence toward the closure is shown as k_on grows (Appendix A).
- **Checked against §13.1's world (S, and the references' run 02):**
  - Early acidification: ρ ≈ 0.031 s⁻¹ and the bound-to-free factor is about 1.5e4. At 1e5 mM⁻¹ s⁻¹,
    λ ≈ 3.8e6 s⁻¹, so the estimated lag is about 1.3e-4 pH. At 1e7 it is about 1.3e-6.
  - Near the steady state (pH ≈ 5): the factor is about 210 and ρ → 0.
  - So both inside cases stay within the budget throughout, and the outside case is out by orders
    of magnitude. Neither was affected by the revision.

D152's charged reactions (§11, item 4) remain the route for **slow** charged kinetics, such as
uncatalysed CO₂ hydration. They are not on FR-4's critical path.

### 4.3 Where the closure acts

- **Every law that needs free H⁺** calls the node's closure on the stage's own state (INNER §7.2,
  stage reads). That means the pump, the proton leak, the pH factor and observations.
- **The stored rows stay the conserved totals.** No projection or rewrite of rows happens anywhere.
- **The H row at a buffered node is H_eq, never free H⁺,** so @3's constant-field law must not read
  it as a concentration. Version 1 refuses an @3 membrane, junction or channel route for H at any
  buffered node. Proton routes there are this note's own laws (§6, §7), which read through the
  closure. At an unbuffered node (the bath, an unbuffered cell) the closure is the identity, h = H̄.
- **The closure is a pure, traced function** of (H_eq, B_tot, V, K_k) per node, in a new process
  module (`laws/reactions/rapid_proton_buffer.py`, with neutral naming).
  - One buffer takes the closed form. Several take a safeguarded Newton in ln h, bracketed by
    [H̄_eq/(1 + Σ B̄_k/K_k), H̄_eq], at a fixed iteration count.
  - Convergence is checked at |g|/H̄_eq ≤ 1e-13, and a failure refuses the step.

### 4.4 The closure's energy

The node's chemical free energy at fixed totals is the minimum over speciation:

    G*(H_eq, B_tot) = Σ_{s ∈ {H, HB_k, B_k}} n_s (μ°_s + RT (ln(c_s/c°) − 1)),   at the closure's speciation,

with μ°(HB_k) − μ°(B_k) − μ°(H) = RT ln(K_k/c°) (**S**: equilibrium).
- **Its derivative** is ∂G*/∂H_eq = μ_H(free), the free proton's potential. So every transport law
  books against the free proton.
- **@3's energy term** is ideal per stored row, RT n (ln(n/V) − 1) on H_eq and B_tot. It lacks the
  speciation's part.
- **The closure therefore owns a declared free-energy term,** ΔG_buf = G* − (@3's term on those
  rows). D152's operator owns its standard-potential term in the same way (D152 §3.3). The term
  enters the energy ledger as stored free energy, not as a flow.
- **The proton's standard part** (15 November 2026: the core's finding, checked by this note's
  owner). @3's stored rows and its reservoir work are referenced to 1 mM with no standard part:
  RT n (ln(n/V) − 1) per row, and μ = RT ln c + zFφ for a held bath. So the term B4's kind books
  is ΔG_buf less the proton's standard part, RT H_eq (μ°(H⁺)/RT − ln c°).
  - It is 0 at an unbuffered node, and ∂/∂H_eq = RT ln(h/H̄), so every route books against the
    free proton as above.
  - Kept in, the part would leave RT ln c° in the ledger for every proton exchanged with a held
    bath. The inner-model note's earlier line, "−RT ln c° per proton at an unbuffered node, not
    zero" (this owner's note of 15 November), is superseded.
  - FR-4's and FR-5's energy identities do not change: their protons stay within the two covered
    nodes, so the part's change sums to zero.

## 5. Fuel and the thermodynamic boundary

### 5.1 Maintained fuel under F2

- **The rows:** ATP, ADP and Pi are inventory rows (F2, D176), declared once with their transformed
  standard potentials at the definition boundary (B3: one authority).
- **In FR-4's first case they are held** at the owner's cytosol. Their amounts do not change, and
  the pump reads their concentrations at each stage. The scope label is "maintained fuel: no
  depletion or recovery". That acceptance is the finite-fuel case's (D176, item 2).
- **The maintenance's booking** per pump cycle:
  - supplied work W = −Δ_rG'_ATP. Since Δ_rG'_ATP < 0, it is positive;
  - the supplied material, recorded as the reservoir records its supply: +1 ATP, −1 ADP, −1 Pi.
  - No pump declares its own ΔG° (INNER §10.2's hole is closed): the pump reads the potentials
    from the one authority.
- **Owners:** the core owner, for held rows in a cell and for B3. FR-4 consumes them.

### 5.2 The boundary between transformed potentials and explicit protons

- **The transformed convention** (the older family's `finite_atp_adp_pi_transformed@1`: "Buffered
  pH/Mg and solvent activity are declared; these are not ionic charges").
  - ATP, ADP and Pi are neutral rows whose potentials are transformed at a reference pH_ref and
    pMg_ref.
  - Δ_rG'_ATP = Δ_rG'° + RT ln(c_ADP c_Pi/(c_ATP c°)).
  - Hydrolysis's protons (about N_H ≤ 1 per ATP near pH 7) are inside Δ_rG'° and are not booked
    explicitly.
- **Per node, version 1 declares one of:**
  - `transformed_at(pH_ref, pMg_ref, band δ)`: fuel reactions and pump hydrolysis may act here. If
    the node also has a dynamic proton row, the run checks |pH − pH_ref| ≤ δ at every stage and
    refuses outside it. The default δ is 0.05.
  - `explicit`: no transformed-potential reaction or hydrolysis acts here (refused).
- **Why a dynamic cytosol may host maintained hydrolysis (S).**
  - Maintained fuel means an external regeneration, so hydrolysis plus maintenance is
    proton-neutral. No hydrolysis proton reaches the cytosol's H row.
  - The only error is the transformed potentials' drift with pH, at most N_H RT ln 10 δ per cycle:
    0.30 kJ/mol at 310 K and δ = 0.05, against |Δ_rG'| of about 50 kJ/mol. It is declared in the
    error budget, and the band check enforces it.
- **Why not hold the cytosol's H row instead (S).** A held H row resupplies the protons the pump
  removes, without the conjugate base the cytosol's buffer would leave behind. That creates charge.
  A buffered dynamic cytosol books it exactly (§3).
- **Version 1 refuses finite fuel at a node with a dynamic proton row.** Regeneration's protons
  would need explicit booking with untransformed species, which is not designed here.

## 6. The proton-pump transporter law

`proton_atp_mass_action_positive@1` is a transporter on a patch: in FR-4, the compartment's bounding
patch. Per cycle it hydrolyses one ATP at the inside node and moves n H⁺ from the inside to the
outside.
- **n** is a declared integer, 1 ≤ n ≤ 4. The worlds here use 2.
- **The cycle's Gibbs energy:**

      ΔG_cyc = Δ_rG'_ATP(inside) + n [RT ln(h_out/h_in) − F V_b],

  with h from each node's closure and V_b = φ_in − φ_out. The pump runs forward when ΔG_cyc < 0.
- **The rate**, in the Na/K law's form (`laws/pumps/kinetic_pump.py`):

      J_cyc = k × a × S × (1 − exp(ΔG_cyc/RT)),
      S = [1 + (K_H/h_in)^n]⁻¹ × [1 + K_ATP/c_ATP]⁻¹.

  - k is the capacity in fmol cycles/s: N × the per-compartment capacity for a lumped node.
  - a ∈ [0, 1] is the availability schedule.
  - K_H > 0 and K_ATP > 0 are in mM.
  - The form vanishes at static head and reverses beyond it.
  - It is evaluated as the Na/K law evaluates its own: log-saturation, expm1 and
    |ΔG_cyc/RT| ≤ 80 as its domain.
- **Effects per cycle:**
  - H_eq(in) −n, H_eq(out) +n;
  - fuel rows held (maintained);
  - charge n e moved outward, which is electrogenic.
- **Energy per cycle:** W = −Δ_rG'_ATP supplied by the maintenance; heat Q = −ΔG_cyc. Each step's
  bookings are exact over the step's cycles, as @3's pumps book theirs.
- **Where it runs:** inside the inner step, at door S's stage `inner` (door S §6), as a declared
  transporter population (INNER §13.3; B5's transporter kind). Each population names its law,
  patch, capacity, fuel node and availability schedule.

## 7. Passive routes on the bounding patch

### 7.1 Counterions and the proton leak

- **Counterions:** @3's own `constant_field@1` on the bounding patch, for K⁺ and/or Cl⁻ (Na⁺
  optionally):

      J_s = P_s A_b u (c_s,in − c_s,out e^{−u}) / (1 − e^{−u}),   u = z_s F V_b/(RT),

  with the limit P_s A_b (c_in − c_out) at u → 0. It books heat.
- **The proton leak:** `proton_constant_field_leak@1`, a new passive law, because the H row at a
  buffered node is not free H⁺ (§4.3). It is the same flux with h_in and h_out from the closures,
  and it books heat equal to the free-energy decrease of what it moves. It meets ARCHITECTURE.md's
  passive contract: closed-pair zero flux at equal μ̃, reversal, dissipation equal to the decrease.

### 7.2 The charged patch: the measured limit, and the route

The charged-patch test (CP; `fr45/charged_patch/CRITERION.md` written first, then `CP_RESULT.md`)
was run on `resolved_pump_tissue@3` alone.
- **The world:** one owner cell in a held bath, and a 250 nm face-free compartment with one route
  on its patch.
- **The reference:** independent, from the two-capacitor constant-field equations.

| Route | dt | dt × G/C_b (log-mean) | Outcome |
| --- | --- | --- | --- |
| Cl⁻, 1.2e-5 cm/s | 1 ms | 1.81 | Refused at run time (domain) |
| Cl⁻ | 0.5, 0.2, 0.1 ms | 0.90, 0.36, 0.18 | Refused: "accounting failed: energy" |
| Cl⁻ | 0.05 ms | 0.090 | Ran; V_b within 8.1e-4 of its change against the reference |
| K⁺, 7.1e-7 cm/s | 1 ms | 0.104 | Refused: energy |
| Cl⁻ × 100 (a pore) | 0.05 ms, 2 µs | 9.0, 0.36 | Refused (domain; energy) |
| H⁺, 6e-5 cm/s, unbuffered | 1 ms | 0.0002 | Ran; reference to 4.3e-6. The lumen drains from pH 5.0 to 5.86 in 0.3 s |
| Run 03, lumped N = 1000 (the floor made negligible): Cl⁻ | 0.1, 0.05 ms | 0.18, 0.090 | Both refused: energy |
| Run 03: K⁺, 7.1e-9 m/s | 1 ms | 0.104 | Refused: energy |
| Run 03: K⁺, 1e-9 m/s, lumen K 100 | 1 ms | 0.043 (max-side 0.051) | Ran; error 1.2e-4 of V_b's change |

- **Nothing was refused in advance:** @3's bound sees G/(C_p + C_b), and every failure was an honest
  run-time refusal.
- **The explicit limit is @3's energy ledger (relative tolerance 2e-3), not stability.**
  - Run 03 removed the absolute floor's help, which had let run 02's single-compartment arm pass
    at 0.090.
  - Passing needs dt × G/C_b ≤ about 0.05 on the max-side G (pass 0.051, fail 0.238), or about
    0.04 on the log-mean (pass 0.043, fail 0.090).
  - G/C_b = P F² c/(RT c_m) is independent of size.
- **Cost:** about 3.6 ms per step in this 3-node world, whatever the observation count. That is
  this runner path's cost and an upper bound for production windows.
- **So, with today's booking (S, upper bounds):** a 900 s FR-4 world with lysosomal Cl⁻ needs dt
  of 0.01–0.03 ms explicitly, of order 25–90 CPU-hours. The FR-5 pore needs 0.1–0.3 µs.

**What refuses: the booking, not the state (run 04).** The energy bound was widened inside the probe
only, and the refused runs were let complete.

| dt × G/C_b (log-mean) | 0.36 | 0.18 | 0.090 | 0.045 | 0.023 |
| --- | --- | --- | --- | --- | --- |
| State error (V_b, of its change) | 1.8e-2 | 3.6e-3 | 8.1e-4 | 1.9e-4 | 4.7e-5 |
| Energy residual / flows | 8.9e-2 | 1.9e-2 | 4.4e-3 | 1.1e-3 | 2.6e-4 |

- **The state is right at the refused steps,** and converges at second order.
- **The residual also converges at second order,** at a steady 5–6 times the state's error. It is
  the second-order quadrature of the patch routes' heat booking. It is not a non-convergent defect
  like FR-10's onset.
- **A third outcome.** The run matched neither reading written beforehand. Those readings expected
  either a wrong state, or a booking error falling more slowly than the state's. So what follows is
  a recommendation for the coordinator and the core owner, not a settled verdict.
- **The trade-off.**
  - Today's energy ledger is the only check that catches an over-large step on these patches.
  - An exact (discrete-gradient) booking would make the energy residual rounding-level at any
    step, and so silence it.
  - With B7 at @3's stability constant 1.0 and an exact booking, run 02's C3 (max-side 0.95, state
    error 1.8%) would pass with nothing to flag it.
- **The options:**
  - **(a) Keep today's booking,** and let worlds declare dt × G_max-side/C_b ≤ 0.05, the energy
    threshold. B7 at 1.0 is then only the stability net. This is conservative: it refuses steps
    whose state is better than 1e-3.
  - **(b) Exact booking plus a state-accuracy constant for B7.** From run 04, max-side 0.24 gives a
    state error of 8e-4 and 0.48 gives 3.6e-3. So a constant of 0.25 bounds the state error at
    about 1e-3 for this law, at five times option (a)'s step.
  - **(c) Exact booking with an embedded error estimate** on the patch routes: a step-doubling or
    embedded-pair state error, checked per step. That makes the guard state-based, not a constant.
  - **Recommended:** (a) now, since FR-4's first world needs nothing more, and (b) or (c) with the
    implicit patch, which books exactly anyway (§7.3). The constant stays open until then.
- **The bound sweep.** I ran a JSON-definition sweep (`b7_sweep.py`), not the inner-model note's
  P3.
  - It covers every JSON world at the tag with passive permeabilities. Pumps and channels on such a
    patch are refused today.
  - It finds the same 10 face-free nodes as FR-1's sweep. Where the term applies, the largest
    term × dt is 0.00068, in older RK4 families.
  - P5 (`pump_water_predictions.json`, ARS at 1 ms) has its node as the gauge, so the term does not
    apply. It would give 0.0032, so it is a near-miss of scope, not of size.
  - The inner-model note's P3 swept the registered and PROPOSED protocols' worlds, Python-built
    ones included, with this term's shape. The term was 0 in every free face-free world, since
    MG0c's carries no ion route, and P5's gauge was excluded.
  - So the term refuses no existing world at any constant.

**The route, in order:**
1. **Now, for FR-4's first world:** explicit, with a small counterion (option (a)).
   - The world declares its own dt with dt × G_max-side/C_b ≤ 0.05, so that today's booking error
     stays under 2e-3. That is a world's choice, not an engine bound.
   - The 0.05 is extrapolated from worlds with no pump and no buffer. FR-4's world must show it on
     its own dt study.
   - The world in §13 uses K⁺ at 5e-10 m/s and 140 mM, so 0.025 at 1 ms. 900 s is 9e5 steps, about
     0.9 CPU-hours at the measured upper-bound cost (**S**).
   - **B7,** as the safety net, host-only: max over free face-free nodes of Σ_m G_m/C_node, at the
     definition beside `explicit_rate_bound`, at the ordinary constant (about 1).
     - It has no run-time half and no 0.05 constant (the inner-model note §7.4 (g) 3).
     - It is statically gated, so worlds without such a node are unchanged.
   - **The world's 0.05 is a declaration, not an engine bound.** FR-4 declares 0.025 on the
     max-side G. Its protocol's dt study enforces it.
   - **State accuracy and the ledgers stay separate parts:** state accuracy (J3, J4) and the heat
     and work closure (J6, J7) are judged apart.
   - **Owner:** `explicit_rate_bound` is the core's file. The core owner, with finding 3's term
     under one D148 record, adds B7 beside it. This note supplies the term.
2. **The implicit patch (§7.3),** FR-1's door 2. Cl⁻ counterions at lysosomal values, and every
   ionic pore of FR-5, wait for it.

### 7.3 The implicit patch: design (the consumer's note designs its route, INNER §13.4)

**Why it can be local (S, from FR-1 §3.1).** A face-free compartment j has one patch, to its owner
i.
- **Its patch voltage is its own:** V_b = −q_j/C_b exactly, whatever φ_i.
- **Its routes conserve q_i + q_j,** so the owner's capacitor row and the global field solve never
  see them.
- **So the stiff mode is local to the compartment.** Its implicit treatment needs no change to the
  global factorization.

**The route kind:** `bounding_patch_implicit_electrodiffusion@1`, one block per compartment.
- **Unknowns at each implicit stage:** the compartment's amounts x_t = n_t,j of the patch's m
  permeant species. m ≤ 16.
- **Everything else,** including the owner's concentrations, is taken from the stage's state. The
  owner's own change during the solve is O(V_j/V_i) and is carried by the same moved amounts.
- **The stage equations, ARS(2,2,2)'s implicit part,** with γ = 1 − 1/√2 and the explicit
  contributions E unchanged:

      R(x) = x − x̂ − γ h J(x) = 0,   J_t(x) = the §7.1 flux of species t into j (fmol/s),
      V_b(x) = −F 10⁻¹⁵ (fixed_j + Σ_s z_s x_s + Σ_{other rows} z n)/C_b.

  x̂ holds the known parts: the step's start, the earlier stage's implicit term, and E.
- **The factor:** the Jacobian is diagonal plus rank one,

      ∂R/∂x = I − γ h (D + u wᵀ),   D_tt = ∂J_t/∂c_j,t / V_j,
      u_t = ∂J_t/∂V_b,   w_s = −F 10⁻¹⁵ z_s / C_b.

  Sherman–Morrison solves it in O(m) per compartment.
- **The solve:** Newton at a fixed count (6), with a residual check, |R_t| ≤ 1e-13 (|x_t| + |x̂_t|).
  A failure refuses the step; nothing is repaired.
- **The update:** the owner's rows change by −Δx, so material and charge are exact by
  construction. The field solve then runs as today.
- **The booking, for the patch as a whole, then split by route.** The patch carries several laws
  in one step: the counterions, the proton leak, the pump, and FR-5's routes. They change the same
  node and the same capacitor, so no one route may take all of ΔG_j or Δ(½ C_b V_b²).
  - **Per node and species,** the divided difference over the step is
    μ̄_t,k = [G_t,k(n_end) − G_t,k(n_start)] / (n_end − n_start). For buffered H_eq it is taken
    on G* at fixed B_tot. For the capacitor it is the mean voltage V̄_b = (V_b,start + V_b,end)/2,
    which is exact for a linear capacitor.
  - **Each route r** that moves Δx_{t,r} from i to j books
    Q_r = −Σ_t Δx_{t,r} (μ̄_t,j − μ̄_t,i) + V̄_b Δq_{j,r} + W_r, where
    Δq_{j,r} = F 10⁻¹⁵ Σ_t z_t Δx_{t,r} is the charge r moves into j,
    with W_r the pump's supplied work, and 0 for passive routes.
  - **Exactness.** The divided differences use each node's total change from all routes. So
    Σ_r Q_r = Σ_r W_r − ΔG_patch exactly, where ΔG_patch is the stored free-energy change the
    patch's routes cause (D152's per-route average-vector-field pattern, §3.3 there).
  - **Attribution.** At the owner, other routes (the plasma patch) also move the rows, so the
    owner's μ̄ attributes their joint change. The per-route split is then exact in sum and O(h²)
    in attribution, and the attribution error is declared and measured.
  - Passive routes satisfy Q_r ≥ 0 by sign. The check refuses a negative passive Q_r beyond
    rounding.
- **The solver ID:** a new IMEX ID (D147), whose stage includes the per-compartment blocks for
  declared patches only. Absent compartments trace nothing.
- **Qualification:**
  - the CP worlds at dt up to 10 ms against the CP reference, at second order;
  - stability on the pore at P × 10⁴;
  - energy closing to rounding with the exact booking;
  - the passive contract on FR-1's closed pair;
  - one planted error, a wrong sign in w, which must fail.
- **Who codes it:** the core's slot runs this per-compartment Newton at each implicit ARS(2,2,2)
  stage, admitted only on a face-free node with exactly one bounding patch (the core's §7.4–7.5).
  The law, its references and its qualification are this note's.
- **The core's two questions, answered.**
  - **What x̂ carries at the last stage.** ARS(2,2,2) is stiffly accurate, so the step's result is
    the last stage. There x̂ = x_n + h [δ E₁ + (1 − δ) E₂] + (1 − γ) h J_I(Y₂):
    - the step's start;
    - the explicit tableau's combination of every other law's rate on the compartment's rows at
      stages 1 and 2 (the pump, the leaks, other routes);
    - the patch's own implicit flux at stage 2's solved state.
    The solve then adds γ h J_I(x). At the first implicit stage, x̂ = x_n + γ h E₁.
  - **How the owner receives the moved amount.** At every implicit stage, exactly −(x − x̂) per
    species. Its known part n̂_i carries what x̂ carries, with the opposite sign for the patch's
    earlier term. In the Newton the owner's concentration follows the solve,
    c_i = (n̂_i − (x − x̂))/V_i. That adds −∂J_j/∂c_i / V_i to the diagonal, keeping it diagonal
    plus rank one (`stage_solve(owner_hat_fmol=..., owner_volume_pL=...)`). The frozen-c_i form
    is an O(V_j/V_i) approximation, kept for tests.
    Material and charge are exact by construction.

## 8. Compartment-state routing

- **Addresses:** every law here addresses "species S in compartment C" through FR-1's identity map
  (door S §6). Reads resolve to C's node, bounding patch and owner.
- **The compartment's state, as laws read it:**
  - free h and pH from its closure (algebraic state, ARCHITECTURE "State roles"; read per stage);
  - V_b (−q_j/C_b at a face-free node, otherwise the field's patch voltage);
  - its amounts;
  - its damage d (§9).
- **Door S:** the pump and the leaks are inner-stage laws. F2's fuel rows are rows, not view fields.
  This note adds no view field.
- **The routing door** (D156's, door S §6) carries FR-5's two control factors to the rate
  multipliers of the leak and transfer laws:
  - **the sources:**
    - d, the injury law's state on the bounding patch (§9);
    - f(pH_C), computed from compartment C's closure, a read of H_eq and B_tot at C's node
      through the identity map;
  - **the sinks:** each FR-5 route declares one control slot, its rate multiplier m_r ∈ [0, 1],
    which the routing door writes;
  - **the combination:** `multiply`, in declared order:
    - m_r = d for a damage route;
    - m_r = f(pH_C) for the conditioned transfer;
    - m_r = f(pH_C) × d where both are declared.

    A factor outside [0, 1] refuses the step.
  - **the timing:** on each stage's state where the routing door supports stage reads (INNER §7.2,
    B4). Otherwise at the split, first order in dt, with that error declared and measured. The
    references use the stage form;
  - **no ledger:** factors book nothing, and the routes book material and heat (§9, §10).
  - **who does what:**
    - the coupling operator's side (reading these sources, writing route controls) goes to the
      operators stream;
    - the contract part (the control slot's declaration and the read of the closure) goes to the
      integration owner;
    - this note specifies both, and the laws are this owner's.

## 9. FR-5: damage, leak and reseal, and pH-conditioned transfer

- **Damage**, `prescribed_patch_injury_resealing@1` (unchanged equation, `legacy/processes/membrane_injury.py`),
  re-expressed as a control state on the bounding patch:

      dd/dt = k_inj u_inj(t) (1 − d) − k_res u_res(t) d,   d(0) = d₀ ∈ [0, 1].

  - u_inj and u_res are declared piecewise-constant schedules in [0, 1].
  - d is kinetic state with no ledger (FEATURE_REQUESTS, FR-5). Its role is continuous dynamical
    state.
  - **On a lumped population, one injury means a uniform one.** d is the damaged fraction of the
    whole population's bounding area, applied equally to every member. That is exact for
    identical members injured alike, and it is what a lumped node can represent.
  - **Injuring one member, or a subset of N₁,** is declared by splitting the population into two
    compartments of the same owner:
    - an injured node with N₁ members, carrying d;
    - an intact node with N − N₁ members, at d = 0.

    FR-1's identity map already holds two compartments per owner. A lumped node never stands for
    a damaged minority.
- **The damage leak:** each declared species s gains a passive route through damage,
  J_s = d P_pore,s A_b × (the §7.1 flux factor). Protons go through the closures, as in §7.1. It
  books heat.
- **pH-conditioned transfer of cargo X** (passive, heat):
  - J_X = f(pH_C) P_X A_b × (the §7.1 flux factor, which at z_X = 0 reduces to
    P_X A_b f (c_in − c_out)).
  - f(pH) = 1/(1 + 10^{m (pH − pH₅₀)}), open below pH₅₀, with Hill slope m > 0.
  - Damage may also scale it, through d's factor.
- **Accounting:** whatever leaves the compartment arrives in the owner's cytosol on the same route.
  Material and charge close in one ledger, and each route books its own heat.
- **FR-5's first world needs no implicit patch (S, answering the lead's question).**
  - Its pores carry only protons and neutral cargo.
  - The proton pore at 1e-6 m/s gives G/C_b ≈ 3.6 s⁻¹ at pH 5 (h ≈ 1e-2 mM), so dt × G/C_b
    ≈ 0.004 at 1 ms. The proton leak gives 0.002.
  - A neutral pore has no charge relaxation. Its material rate P A/V is about 12 s⁻¹ (0.012 at
    1 ms), within finding 3's term.
  - The K⁺ counterion is FR-4's, at 0.025.
  - So the implicit slot is needed only for ionic pores and Cl⁻ counterions, which come later.
- **What runs when:**
  - proton and neutral leaks and transfers run explicitly now. Their rates are small, for example
    H⁺ at 6e-5 cm/s gives dt × G/C ≈ 0.0002 at 1 ms;
  - ionic pores (K⁺, Cl⁻, Na⁺ through d) wait for the implicit patch (§7.2), and are refused until
    then.

## 10. Accounting and floors

- **Material:**
  - H_eq and every B_tot,k are conserved, except across routes;
  - the pump moves n H_eq per cycle;
  - the fuel rows are held, and the maintenance records its supply.
- **Charge:** the node charges use the stored rows exactly (§3). The pump and the ionic routes move
  charge, and the field follows.
- **Energy:**
  - the ledger closes with the stored free energy (@3's term, plus the closure's ΔG_buf, plus the
    capacitor energy);
  - plus heat from the pump, the leaks and the counterions;
  - minus the maintenance's supplied work W.
- **Floors (CP4):**
  - the material floor for H must be species-scaled, at most 1e-16 fmol for single compartments;
  - @3's absolute energy floor (2e-8 pJ) is 6% of a single compartment's per-step pump energy, so
    energy acceptance uses lumped populations that push it below 1e-4 of that energy, plus D150's
    guards of record: a species-only guard world and a NumPy ΔG test per law.

## 11. What today's code refuses, with owners

The table is as written on 15 November. Its status on 16 November:
- **Rows 1 and 2:** lifted for FR-4's kinds by refusal 4 version 1.1, on main
  (CLOSED_COMPARTMENT_DESIGN §3.4.1).
  - A constant-field permeability is admitted only when the world declares kinds.
  - @3's own pumps and channels stay refused.
  - Cl⁻ and ionic pores still wait for the implicit patch (§7.3).

| # | Refused today | Where | Owner and route |
| --- | --- | --- | --- |
| 1 | An ion route on the bounding patch (nonzero permeability or channel) | `compartments.py`, refusal 4 | **This note's owner** (`compartments.py`). Lifted for small (K⁺-class) routes with B7 as the safety net and a world-declared dt (§7.2, step 1). For Cl⁻ and pores, lifted with the implicit patch (§7.3): this owner designs and qualifies it, and the core owner's answer on the numerical-plan slot decides who codes it |
| 2 | A transporter (pump) on the bounding patch | `compartments.py`, refusal 4; there is no transporter kind | **This owner** (the pump law, §6, and the lifted refusal). B5's transporter kind and its insertion point in the inner step: **the core owner** (A1) |
| 3 | ~~Reactions inside a compartment~~: **not refused** (dropped) | — | **Confirmed by a host-side parse** on the tag's snapshot (`fr45/charged_patch/refusal3_parse.py`). FR-1's world W with a neutral D152 reaction is admitted at the compartment node, and at that node with its owner. The planted held-bath site is refused with D152's message. One format rule applies: omit the `cells` key rather than give an empty list. Beside a bath dose, door S's whole-field `CONFLICTS_VIEW` is the integration owner's case (A6), not this list's |
| 4 | Charged reactions | `species_common.parse_species` refuses nonzero valence | **This owner** (`species_reactions.py`; not started, since no FR-4 or FR-5 world needs it). Version 2 admits closed charged reactions with Σ_s z_s ν_s = 0 exactly, in integers, for **slow** kinetics, and rewrites D150 §3's exact-zero charge argument. Buffering is not this route (§4) |

Two more, which this note adds:
- an @3 route for H at a buffered node (§4.3);
- finite fuel at a node with dynamic protons (§5.2).

## 12. Species budget against the cap of 16

| World | Rows | Count |
| --- | --- | --- |
| FR-4, first | Na, K, Cl, H, B_c (the cytosol's buffer, pK 7.2), B_L (the lumen's, pK 6.0), ATP, ADP, Pi. A buffer species has one pK, so two pKs need two rows | 9 |
| FR-5, first | FR-4's 9 + cargo X | 10 |

All fit under 16 (D165), and none needs a raise.

## 13. The first acceptance worlds

These are generic. Each declares a lumped population of N = 1000 identical compartments, of
radius 250 nm each, as one node.

**Common to both:**
- **Temperature:** 310 K.
- **The owner:** a sphere of radius 10 µm (4.18879 pL; plasma patch 1.25664e-9 m², 0.01 F/m²),
  impermeant, with no pump, in a held bath of Na 145, K 5, Cl 110 mM and pH 7.4. Unbuffered
  bath.
- **The lumped compartment:**
  - V = 1000 × 6.54498e-5 pL = 6.54498e-2 pL;
  - A_b = 7.85398e-10 m²;
  - C_b = 7.85398e-12 F.
- **The cytosol:** Na 10, K 140, Cl 10 mM.
  - Buffer B_c (base valence −1) with B_tot 50 mM, starting at pH 7.2. B_L does not apply there:
    it carries the declared trace, 1e-9 mM, undeclared to the closure.
  - **B_c's registry entry:** with μ°(H⁺) = 0, (μ°(HB_c) − μ°(B_c))/RT = −7.2 ln 10 = −16.57856, so
    pK 7.2 follows (§4.1), at the declared `standard_concentration_mM` = 1000. k_on = 1e7 mM⁻¹ s⁻¹
    sits on the closure's declaration (envelope and reference only).
  - **Absent rows:** every row that does not apply at a node carries a declared trace of 1e-9 mM;
    B_c, B_L, ATP, ADP and Pi declare `background` (trace 1e-9 mM, floor 1e-18 fmol). The fixed
    charges come from fsum(z n) of the written amounts. The references use an exact 0 for the
    absent buffer, a declared difference the protocol discloses.
  - Held fuel: ATP 3, ADP 0.3, Pi 3 mM. Δ_rG'° = −30.5 kJ/mol (a generic declared value).
  - `transformed_at(7.2, pMg 3, δ 0.05)`.
- **The lumen:** Na 10, K 140, Cl 10 mM.
  - Buffer B_L (base valence −1) with B_tot 40 mM, starting at pH 7.2 (a resolved start). B_c,
    ATP, ADP and Pi carry the declared trace.
  - **B_L's registry entry:** (μ°(HB_L) − μ°(B_L))/RT = −6.0 ln 10 = −13.81551, so pK 6.0; its
    k_on, 1e7 mM⁻¹ s⁻¹, is on the closure's declaration.
  - Mode `explicit`.
- **Initial proton equivalents** at each node: H_eq = V (h₀ + Σ_k B̄_k h₀/(h₀ + K_k)), with
  h₀ = c° 10^{−pH₀}.
- **Fixed charges:** each node starts electroneutral. fixed = −(H_eq + Σ_k z_k B_tot,k +
  Σ_ions z n), so q = 0 and V_b = 0.
- **The voltage domain.** @3's −120 to 60 mV domain applies only to channel populations
  (`surface_pump_v3.channel_domain_valid`), and the bounding patch carries none. So the negative
  control's V_b of about −0.27 V is admissible (code reading). The pump law's own domain,
  |ΔG_cyc/RT| ≤ 80, holds there.

### 13.1 FR-4: buffered acidification against a gradient

- **The patch:**
  - the pump: n = 2; k = 8.3027e-3 fmol cycles/s for the node (5,000 cycles/s per member × 1000
    members ÷ N_A × 10¹⁵); K_H 1e-4 mM, K_ATP 0.1 mM, a = 1;
  - the proton leak, P_H 6e-5 cm/s (6e-7 m/s);
  - the counterion K⁺ at 5e-10 m/s (5e-8 cm/s). For the lumped node that is G_K ≈ 2.0e-10 S,
    which carries the pump's early current, about 0.44 pA (2,760 H⁺/s per member at S ≈ 0.276), at about 2.2 mV (**S**).
- **The run:** 900 s, explicit at dt = 1 ms (dt × G_K/C_b = 0.025 on the max-side G), with B7.
- **What it shows:** lumen pH falling to a steady state where pumping balances the leak; K⁺ leaving
  in step with the pumped charge; V_b small.
- **The negative control:** the same world with P_K = 0.
  - **S:** Δ_rG'_ATP = −51.4 kJ/mol at the held fuel, so the pump charges C_b to its static head,
    V_b ≈ −0.266 V, after moving about 2.2e-5 fmol per member.
  - The lumen buffer holds about 3.4e-4 fmol per pH unit per member at pH 7.2 (β ≈ 5.1 mM/pH;
    **S**).
  - So acidification stalls after about 0.06 pH units. With the route, the drop is of order one
    or more units, which the reference confirms.
  - The references agent confirms that the effect exceeds the declared budget by orders of
    magnitude (D176, G1/G3).
- **Checked:**
  - H_eq, B_tot and the counterion's amounts against the reference;
  - V_b;
  - the pump's cycles;
  - the energy identity (stored change + heat = supplied work);
  - the cytosol's pH band;
  - the material floors.

### 13.2 FR-5: damage, leak, reseal and pH-conditioned transfer, on the same state

**Revised after the references' R-transfer runs** (`validation/compartment_ph/REFERENCES_USAGE.md`;
evidence in `independent-references-20261115-01/compartment-transfer-crosschecks-01/`). The first
version showed neither of its claims.
- **No release burst.** X crossed while the lumen was still acidic (f ≈ 0.98, τ ≈ 8 s), so
  little was left for the pore at 100 s.
- **The condition never closed.** A 1e-6 m/s proton pore raised the proton permeability only
  2.7-fold. The lumen's pH peaked at 5.24, below pH₅₀ = 5.5.
- **Its controls had no X budget,** and its start time was undefined: FR-4 is 1.4e-3 pH from its
  steady state at 900 s.

So the world now has two arms (`parameters.ARM_T`, `ARM_R`). Each claim is shown by the arm that
isolates it.

**Common to both arms:**
- **The start:** FR-4's engine checkpoint at t = 1800 s, its steady state (pH_L ≈ 5.0946 per the
  references). The references receive it as `tr.Start`, and FR-5's t = 0 is that checkpoint.
- **Cargo X** (valence 0) at 1 mM in the lumen and 1e-4 mM in the cytosol and bath. That is a
  resolved start: the energy ledger refuses trace starts.
- **The condition:** f with pH₅₀ 5.5 and m 4.
- **Damage:** k_inj 1 s⁻¹ during the arm's window, then k_res 0.05 s⁻¹.
- **The proton pore:** 1e-5 m/s through the closure.
  - **S:** at full damage the lumen's steady pH rises to about 6.2, so f falls to about 1.6e-3.
  - It stays explicit at 1 ms: max-side dt × G/C_b ≈ 0.029 at pH 5.1, within the world-declared
    0.05.
- **Horizon and step:** 400 s at a declared 0.5 ms. Ionic pores are refused in version 1 (§9).
  - **The step bound is on the patch total.** The world's 0.05 (max-side dt × G/C_b) applies to
    the sum over every route on the bounding patch, because those routes share one charge mode (V_b).
  - The references' rerun measured the patch total at 0.048 at 1 ms: the proton pore 0.029, plus
    the leak and K⁺.
  - So FR-5 declares 0.5 ms (about 0.024), FR-4's factor-of-two margin. Price: 8e5 steps per
    400 s run instead of 4e5, about 0.8 CPU-hours per run at the upper-bound cost.
  - **Confirmed by the references' readout** (branch 931fb38a,
    `compartment-transfer-arms-01-readout.*` beside their record). It reran the record's own
    worlds from its own snapshot and reproduced the record exactly. Each arm's results are given
    in its own entry below.
  - **The start is required for X's budget.** X_L along the run moves by about 0.06 B per 1e-3
    pH of start offset. So the X comparison must start the reference from the engine's own
    1800 s checkpoint (`tr.Start`), not from a recomputed steady state.

**Arm T, the condition:**
- **Parameters:** P_X = 1e-9 m/s (τ ≈ 83 s at f ≈ 1); a proton-only pore (P_pore,X = 0); damage
  during [60, 120] s.
- **What it shows** (restated after the references' rerun, 071ef983):
  - X crosses while the lumen is acidic.
  - The damage raises pH_L above pH₅₀. While pH_L > pH₅₀, the conditioned transfer's mean rate
    falls at least 10-fold below its mean rate before damage, judged on the route's cumulative
    transfer in units of X's budget B.
    - The readout measured 8.375 B/s over [0, 60] s against 0.6120 B/s over [73.081, 326.882] s,
      a ratio of 13.69.
    - The route slows but does not stop. Most of the transfer happens while f passes through its
      half-open range, and longer windows do not change that.
    - So the claim is a number, not "stops".
  - After resealing, pH_L returns below pH₅₀ before 400 s, within 5 s of the reference's crossing
    time, and the transfer resumes. The readout's crossings: above at 73.081 s, back below at
    326.882 s.
- **Control:** f ≡ 1. X keeps crossing through the alkaline window.

**Arm R, the release:**
- **Parameters:** P_X = 1e-10 m/s (τ ≈ 830 s), which keeps most X in the lumen until damage, as the
  references' grid showed; a cargo pore at 1e-6 m/s (τ ≈ 0.08 s at d ≈ 1) beside the proton
  pore; damage during [100, 160] s.
- **What it shows:**
  - a release burst through the pore: at least 0.8 of X_L(0) released inside the window. The
    readout measured 0.8736 over [100, 160] s. The conditioned route carries nothing while
    pH_L > pH₅₀, since the burst has already equalised X;
  - the pH rising during damage;
  - after resealing, pH_L returns below pH₅₀ before 400 s, within 5 s of the reference's crossing
    time. The readout's crossings: above at 113.081 s, back below at 366.882 s.
  - Full recovery to within 0.001 of the start needs about 820 s. That is not claimed, so the
    horizon stays at 400 s.
- **Control:** d ≡ 0. No burst, and no pH rise.

**X's budget, declared for G1 and G3:**
- |X_L,engine − X_L,reference| ≤ 1e-3 of the lumen's initial X at every record. The same budget
  applies to the conditioned route's cumulative transfer, in fmol: 1e-3 × X_L(0) × V_L.
- Each control must differ from its arm by at least 10 times that budget, on the same quantities.

**Every book closes:**
- X's and H_eq's material across both nodes;
- charge;
- energy (stored change + heat = the maintenance's work);
- the cytosol's pH band.

## 14. Qualification, and what waits on whom

- **Numerical verification first,** against references written from Appendix A by a separate agent:
  - dt studies at second order;
  - the closure against Appendix A.2's kinetic reference, as a convergence series in k_on. This is
    D175's reduction check, with §4.2's envelope and budget declared before the comparison, and
    its outside case (k_on = 1 M⁻¹ s⁻¹), which must fail;
  - the implicit patch's qualification (§7.3), when it is built;
  - the passive contract for the proton leak (§7.1) on FR-1's closed pair. The Syn3A track's P0e
    found two closed topologies on main.
- **G1/G3 (D176):** exact contract tests per law (a NumPy ΔG per step), plus the scientific negative
  controls of §13, whose effects exceed the budget.
- **Waits:**
  - FR-4's code waits on:
    - B5's transporter kind, held rows and B3 (the core owner);
    - B7 as the host-only stability safety net beside `explicit_rate_bound` (the core's file,
      with the D148 round);
    - the identity map (FR-1's re-gate).
  - FR-5's code waits on FR-4, the routing door (§8: the operators stream and the integration
    owner), and the injury law as a control state.
  - Ionic pores and Cl⁻ counterions wait on the implicit patch (§7.3). Whether it fits behind one
    slot in the numerical plan, which decides who codes it, is the core owner's answer.
  - The exact booking of patch routes (§7.2) comes with the implicit patch. Until then, explicit
    worlds declare dt × G/C_b ≤ 0.05.

## 15. Open questions

1. **Is the explicit K⁺-counterion world (§7.2, step 1) an acceptable first FR-4 acceptance,** with
   Cl⁻ and pores following the implicit patch? **Recommended: yes.** It is the shortest path to a
   working FR-4.
2. **Where should the closure's per-stage call sit:** in the transporter kind's evaluation (this
   owner's laws only, as proposed), or as a general algebraic-state read in the core (B1/B4) that
   any law may use? **Recommended:** this owner's laws first, then promote it when a second
   consumer (FR-6's pH-dependent gating) needs it.
3. **The pump's stoichiometry and capacity** come from evidence records when a calibrated world is
   wanted. The values here are generic.

## 16. FR-5 on the kind interface (design, 16 November 2026, before code; D142)

**Status: accepted (the lead's rulings, 16 November 2026), with these answers to §16.8:**
1. The routing door is accepted as designed, and the **core** builds it, as part of the kind
   interface (D180's public surface). It may refine the API.
2. The core changes `passive_routes`.
3. d is made exact at every step end from the integrated hazards, and the kind's tests show it.
4. The schedules take the core's gap-6 format, with breakpoints joining `experiment.changes`.
5. No `@2` if it can be avoided: the multiplier field exists only when some route declares factors,
   so FR-4's structure stays untouched. `passive_routes@2` is the core's fallback, with a reason.

**Built on fr45-next:**
- the two source kinds, without their door hooks' registration (module functions until the seam
  lands) and with zero schedules until gap 6;
- refusal 4 version 1.2 (CLOSED_COMPARTMENT_DESIGN §3.4.2);
- FR-5's start part (§16.6).

FR-4 now runs as kinds (`cells.rapid_proton_buffer@1`, `cells.transporter@1`,
`cells.passive_routes@1`; INNER §7.4 (k)). This section puts §8 and §9 on the same interface. The
equations are §9's, unchanged, and R-transfer (`validation/compartment_ph/transfer_reference.py`)
computes the same ones. Where §8 or §9 differ (the split-timing fallback, "a control state"), this
section supersedes them. **S** throughout: no FR-5 world has run.

### 16.1 What FR-5's world needs from the engine

- **The damage** d per damaged patch, with dd/dt = a(1 − d) − b d, a = k_inj u_inj(t) and
  b = k_res u_res(t).
  - u_inj and u_res are piecewise-constant schedules in [0, 1].
  - d is exact at every step's end, since the protocol's J2 reads d "at rounding on every rung
    pair". It stays in [0, 1] and books nothing.
- **Three routes on the bounding patch,** each one of FR-4's laws scaled by a rate multiplier
  m_r ∈ [0, 1]:
  - the conditioned transfer: X by `passive_neutral_permeation@1`, with m = f(pH_L);
  - the cargo pore (arm R only): X by the same law, with m = d;
  - the proton pore: H by `proton_constant_field_leak@1` through the closure, with m = d.
- **The factors:** m_r is the product of the route's factors in declared order.
  - They are evaluated on each stage's state. This is the stage form: second order, as the
    references compute it.
  - A factor outside [0, 1] refuses the step. Factors book nothing.
- **The bookings.** The cargo routes keep §7.5's exact booking: X is moved by them alone, and the
  protocol's J7 ruling reads them that way. The proton pore keeps the tableau's booking, and its
  slope × m joins B7's stage term.
- **Observations:** d, f, and each route's cumulative transfer and heat (the generator's
  `ENGINE_READOUTS`).
- **The start:** FR-4's declared world at 1800 s (§16.6).

### 16.2 The design: two source kinds, one routing door, the passive routes as its sink

One owner per entity:

| Entity | Kind (module) and law | Owner | State and controls | Exposes |
| --- | --- | --- | --- | --- |
| A patch's damage | `cells.patch_damage@1` (`kinds/patch_damage.py`); law `cells.bounding_patch_damage@1` (`laws/transport/patch_damage.py`) | FR45 | d and the integrated hazards [damage]; controls u_inj, u_res [damage], scheduled (gap 6) | the factor d, per damage entity |
| A node's pH condition | `cells.ph_condition@1` (`kinds/ph_condition.py`); law `cells.ph_conditioned_factor@1` (`laws/reactions/ph_condition.py`) | FR45 | none: algebraic, from the stage's read | the factor f(pH), per condition; the readout column f |
| A route's rate multiplier | `cells.passive_routes@1`'s reserved `factors` key | CORE's insertion, FR45's kernels | control `passive_multiplier` [route], written by the door | — |
| The routing door | a seam in `kind_registry.Kind` and `surface_pump_v3` | CORE | — | writes each routed control slot at every stage |

**`cells.patch_damage@1`** (model key `patch_damage`):

```json
"patch_damage": [{"id": "damage_0", "patch": "bounding_0", "law": "bounding_patch_damage@1",
                  "initial_damage": 0.0, "injury_rate_per_s": 1.0, "resealing_rate_per_s": 0.05}]
```

- **Admission:** at most one damage entity per membrane patch, on any patch. The law is general,
  as the older family's injury of plasma patches is; FR-5 declares the bounding patch. The ID is
  unique among the definition's entity IDs, d₀ ∈ [0, 1], and both rates are finite and ≥ 0.
- **State:** `patch_damage` (d) and `patch_damage_injury_hazard`, `patch_damage_resealing_hazard`,
  each [damage]. The hazards are the cumulative ∫a dt and ∫b dt, dimensionless; the older family
  keeps such integrals too (`damage_opened`, `damage_closed`).
- **Controls:** `patch_damage_injury` and `patch_damage_resealing` [damage], the schedules (§16.4),
  in [0, 1] by the kinds' default rule.
- **`rates`:** derivatives only. d' = a(1 − d) − b d at the stage's d gives the stage values the
  routes read (second order); the hazards' derivatives are a and b. There are no node rates, no
  heat and no work, and `valid` is the kernel's domain.
- **`book`:** d's end value is replaced by the exact solution over the step,
  d_end = d_eq + (d_start − d_eq) e^(−(A+B)) with d_eq = A/(A + B) (`patch_damage.exact_step`).
  - A = dt × applied(injury hazard) and B = dt × applied(resealing hazard). Within a step a and b
    are constant, so this is exact. `applied` reaches a kind's own fields: `rates`' derivatives
    enter the stage's rates by name (`surface_pump_v3._with_kind_derivatives`; read in code).
  - The applied rate is used, not the difference of the cumulative fields. That keeps A at one
    rounding of a dt; the difference would lose about |hazard|/(a dt) ulps, near 1e-11 relative
    late in a window at 0.5 ms.
- **`domain`:** d ∈ [0, 1] and finite hazards, traced on the device. It has no `ledger_terms` and
  no `stage_term`, since d moves nothing.
- **As a factor source:** d per damage entity, at the stage's state.

**`cells.ph_condition@1`** (model key `ph_conditions`):

```json
"ph_conditions": [{"id": "acid_0", "node": "lumen_0", "law": "ph_conditioned_factor@1",
                   "ph50": 5.5, "slope": 4.0}]
```

- **The node by its ID.** A kind's parse sees the base model's nodes, not FR-1's identity map, so
  the condition names the compartment's node. In the declared world FR-1's operator gives that
  node its identity.
- **The factor:** f = 1/(1 + 10^(m (pH − pH₅₀))) (`ph_condition.factor`), with pH = −log₁₀(h/1 M).
  h is the read's free h at the node; at an unbuffered node it is the stored row. This is B4's
  readout convention (`rapid_proton_buffer.PH_REFERENCE_mM`).
- **Admission:** a finite pH₅₀, a slope > 0, an existing active node, and unique IDs.
- **No state.** `readouts` gives f per condition as an observation column; its domain is the
  read's.

**The routing door** (CORE). This is the seam in the form proposed here; the core's design decides
the form.
- **Sources:** a kind declares `factor_sources(declaration)` → (entity ID, ...) and
  `factors(read, p, *, xp)` → its [source] values, from its own fields and the stage's read state,
  never another kind's fields.
- **Sinks:** a kind declares `routed_controls(declaration)` → ((control field, slot, (source ID,
  ...)), ...).
- **Binding** resolves every named source. It refuses an unknown ID, an ID two kinds expose, and a
  slot routed twice.
- **At every stage,** after the stage read and before any kind's `rates`, `stage_term` or
  `readouts` (observed rows included), each routed slot becomes its own control value × Π its
  sources' values in declared order.
  - The product is a left fold, so its rounding is fixed.
  - It is written into the control every kind receives.
  - The kinds' [0, 1] rule then refuses a factor or a product outside [0, 1]; each source's
    values are checked in [0, 1] too.
- **No ledger and no state.** With no sink declared the door is absent (A4). A sink's new control
  field is another matter: a kind's control fields are static, so the field changes the structure
  of every world that declares the sink kind, FR-4's included (question 5).
- **Why a control slot,** rather than passing factors to the hooks: every hook keeps its
  signature, and the sink reads only its own field, so there is no cross-kind read. Scheduled
  controls (gap 6) and routed ones compose: a slot's own value may itself be a schedule.

**The sink, `cells.passive_routes@1`:**
- **Factors:** a route's `factors` is a list of source IDs, in declared order.
- **The slot:** the kind adds the control field `passive_multiplier` [route], 1 from
  `control_values`, and declares each factored route's slot in `routed_controls`.
  - **This changes FR-4's structure.** `surface_pump_v3._kind_types` builds the Control type from
    each declared kind's static `control_fields`, keyed by the kind IDs alone (read in code). So
    FR-4's world, which declares `cells.passive_routes@1` without factors, would gain the field:
    a new Control type and compile key. Its records would stay bitwise equal, since an opening × 1.0
    is exact. Question 5 gives the options.
- **Its use:** each route's opening is multiplied by it in `rates`, `stage_term` and the readouts.
- **What does not change:** §7.5's booking, `bound_rate` (its bound holds at m ≤ 1), `moved_rows`
  and the exact scope (`_exact`). So FR-5's cargo routes are booked exactly, and the pores and the
  leak by the tableau.
- **Ionic pores stay refused** by construction (§9): the leak's law carries only the proton row,
  and the neutral law only valence 0.

### 16.3 Why this design, against the alternatives

1. **d inside `passive_routes`** (no routing seam): rejected. It ties a patch's state to one
   consumer, so a channel population or a transporter could never read d, and it puts FR-5's
   physics in the core's file.
2. **FR-5's routes in a new kind of this lane's** (no routing seam): rejected.
   - It duplicates `passive_routes`' kernels, booking and B7 terms.
   - The cargo pore and the conditioned transfer would sit in two kinds on one row, X. Each would
     see the other as another mover, so both would lose §7.5's exact booking, which the protocol's
     J7 ruling assumes.
3. **The door at the split** (an operator writing route controls between steps, §8's fallback):
   rejected. It is first order in dt during damage, so FR-5's J2 classes for X and pH (second
   order) would fail by construction.
4. **d exact at the stages too,** through a kind relaxation seam: the core would advance a kind's
   linear-relaxation field exactly at each stage fraction, as `stage_gates` advances channel gates
   (`exponential_gates.advance`). It is not needed for second order, so it is offered as a later
   improvement. The baseline needs nothing beyond gap 6 and the door.
5. **`control` passed to `book`** would replace the two hazard fields. The hazards need nothing
   from the core and are observables. Either works; the core decides.

### 16.4 What FR-5 needs from the core's gap 6 (time-varying kind controls)

- **Schedules:** a kind's control field may be a piecewise-constant schedule declared in the
  definition, its values in [0, 1] (or the kind's `control_domain`). The format is the core's
  design's; FR-5's draft writes `experiment.damage_controls`, one entry per damage entity, with
  `injury` and `resealing` lists of {time, value}.
- **Breakpoints:** every breakpoint joins `experiment.changes`.
  - That covers the EventGrid, `event_index`, and the vector path's `held_controls`, which
    refuses a control that varies within a held segment.
  - So each step's control is the schedule's value on that step, and a checkpoint restores its
    event position.
- **`control_values(spec, declaration, times)`** keeps its signature and returns the schedule at
  each step's start.

FR-5's breakpoints (60 and 120 s in arm T, 100 and 160 s in arm R) lie on every rung's grid.

### 16.5 Checks and tests, before any judged use

- **The kernels** (exist; tests in `test_fr45_damage_and_worlds.py`):
  - `exact_step` against the closed form in high precision;
  - d ∈ [0, 1] at any h;
  - composition: two half steps equal one step at constant rates, to rounding;
  - f(pH₅₀) = 1/2, monotone, in [0, 1] without overflow;
  - the multiply's [0, 1] check.
- **The kinds:**
  - parse and refusals;
  - a damage run whose records equal the closed form at rounding on piecewise schedules, and d
    unchanged under zero schedules;
  - a route with factor d at a held d equals a route of permeability d P, to rounding;
  - a condition's f equals `ph_condition.factor` of the closure's pH readout;
  - a factor above 1 is refused, and so is an unknown source;
  - an undeclared kind is absent, and FR-4's records are bitwise unchanged on both paths; FR-4's
    structure and compile key are unchanged too under question 5's options (a) and (b), not (c);
  - the hooks trace on the device.
- **Planted errors,** each of which must be caught:
  - the condition read at the cytosol instead of the lumen (the X budget against R-transfer);
  - the injury schedule shifted by one step (d's exactness);
  - the factor applied twice to the proton pore (the pH budget against R-transfer).
- **FR-5's world:** both arms' quick passes against R-transfer, started from the engine's own quick
  start. Then FR-5's dt study (`dt_study.FR5_CRITERIA`), the rehearsal and registration, as FR-4's.
- **Refusal 4, version 1.2** (`compartments.py`, this lane's file). Version 1.1 fails closed on any
  kind outside `ROUTE_KINDS` and `READ_KINDS`, so it would refuse FR-5's declared world.
  - Version 1.2 admits the two kinds as factor kinds: they move no row and carry no charge.
  - The declared world is then shown bitwise equal to the development world, as FR-4's was. FR-5's
    protocol's correction of 16 November expects this.

### 16.6 FR-5's start: FR-4's checkpoint at 1800 s

- **The run:** the generator's `start` part runs FR-4's declared world at 1 ms to 1800 s (1.8e6
  steps, about 30 min on the vector path).
- **What it writes:**
  - the engine's snapshot of the final state (`cells.records.io.write_snapshot`, in OUT/start/
    engine_snapshot), for provenance;
  - the start extract (`definitions.start_extract(producer="engine", ...)`): each node's nine rows
    and its charge (`surface_pump_v3.node_charge` of the final state), the last record's pH_c, pH_L
    and V_b, the time, the step, and the snapshot's identity.
- **How FR-5's parts use it:** they build their definition from the extract
  (`definitions.fr5_world(start=...)`: the amounts, the charges and the fixed charges that follow,
  with X at its declared start). They never load the snapshot, since FR-5's world has another
  structure: the X row and three more kinds. The references read the same extract (`tr.Start`).
- **Two fixes found while designing:**
  - `fr5_world` adds a top-level `start` record, which `parse_spec` refuses (a definition holds
    exactly schema_version, model, experiment and execution). It moves into the part's record,
    where the generator's `_with_start` already records the extract's identity.
  - The drafted condition names FR-1's compartment ID, which a kind's parse cannot see. It names
    the node instead.

### 16.7 Who does what, and the cost (agent-days, S)

- **FR45 (this lane):**
  - the two kinds, with their tests and planted errors: 1–1.5;
  - the start part and its extract: 0.5;
  - FR-5's world in the kinds' forms, refusal 4 version 1.2, the generator's stand-ins removed,
    and the quick passes against R-transfer: 0.5–1;
  - then FR-5's dt study and rehearsal, on CPU.
- **CORE:**
  - gap 6 (in progress);
  - the routing door, with a planted source and sink under `tests.`: about 0.5–1;
  - `passive_routes`' sink (`factors`, `passive_multiplier`): about 0.25. This lane can write it
    for the core's review instead, as the lead assigns.

### 16.8 Questions for the lead and the core

1. **The routing door:** as §16.2 states it (sources, routed control slots, at every stage), or the
   form the core's gap-6 design has already chosen?
2. **`passive_routes`' sink:** the core's change, or this lane's for the core's review?
3. **d's exactness:** the hazards through `applied` (no seam), or `control` passed to `book`?
4. **The schedules' format** (gap 6).
5. **The sink's control field and FR-4's structure** (§16.2, "The slot"). The options:
   - (a) per-declaration fields: the core's types keyed by each kind's structure entry, so the
     field exists only where a route declares factors (a core change to schema A);
   - (b) a new version, `cells.passive_routes@2`, with `factors` and the slot, in the same module:
     FR-4 keeps @1 and its structure, and FR-5 declares @2 for all its passive routes, the leak
     included (recommended: no schema change, and FR-4's qualification is untouched);
   - (c) accept the change: FR-4's records stay bitwise equal, but its Control type and compile
     key change, after its dt study and before its judged run, so the rehearsal would no longer
     run the dt study's program.

## 17. Finite fuel on the kind interface (design, 16 November 2026, before code; D142, D176 item 2)

**Status: accepted, ruled by the lead on 16 November 2026 (§17.5), within D176 item 2.** It is
built after FR-5's dt study is launched. Tags: **(code)** read in code on main 7c8bfa47; **S** this
owner's arithmetic.

### 17.1 What it is, and what it claims

- **The feature.** `cells.transporter@1` gains its second fuel kind, `finite_fuel_rows@1`. The pump
  moves its ATP, ADP and Pi rows, one ATP to ADP + Pi per cycle, so fuel can deplete and recover
  when a reaction regenerates it. Maintained fuel (`maintained_held_rows@1`, §5.1) is unchanged.
- **Its first world is R-fuel** (`validation/compartment_ph/fuel_reference.py`; REFERENCES_USAGE
  "Finite fuel"), the lead's option (a) of 15 November and D176 item 2:
  - a neutral solute Y pumped into a store;
  - D152's passive regeneration D + ADP + Pi ⇌ P + ATP, stopped on [100, 300) s;
  - Y's leak back.

  The proton pump stays on held fuel. Finite fuel at a node with a dynamic proton row is still
  refused (§5.2) and is out of scope here.
- **The claim:** numerical verification against R-fuel only (D174's first kind). There is no
  calibration and no living-cell claim.
- **Engine models it runs:**
  - `resolved_pump_composite@1` over `resolved_pump_tissue@3`;
  - `cells.transporter@1` with `atp_driven_transporter_mass_action_positive@1` on
    `finite_fuel_rows@1`;
  - `cells.passive_routes@1` with `passive_neutral_permeation@1`, for Y's leak;
  - `local_species_reactions@1` with `ideal_detailed_balance_mass_action@1` and its
    `reaction_controls` schedule, for the regeneration;
  - under ruling D2's recommendation, `cell_owned_compartments@1` for the store.

### 17.2 The kind's finite-fuel path

On the core's gap-2 seams (INNER_MODEL_V4_DESIGN §7.4 (m), landed):
- **Moves:** per cycle, ATP −1, ADP +1 and Pi +1 at the fuel node (the patch's inside cell), and
  n of the role across the patch.
  - Today, `moved_rows` already lists finite fuel's rows, and the parse refuses the fuel kind
    (`GAP_FINITE_FUEL`) **(code)**.
  - To be written: the rates' fuel moves, the stored rate and the two ledger roles below.
- **Stored energy:** the standard part of the fuel rows' change, booked as `stored_pJ` (per
  cycle × cycles) and as its rate `KindRates.stored_pJ_s` (per cycle × J_cyc). One helper serves
  both. That is (m)'s rule for a kind's author: @3's RT ln c terms carry the rest.
  - **Its frame.** @3's rows carry RT n (ln(n/V) − 1), with n/V in mM: a 1 mM frame with no
    standard part. So each row's standard part is μ°' = RT (μ°/RT − ln c0), with μ°/RT the
    registry's at its c0 in mM. That is D152's own convention (§3.3 of its note).
  - Hydrolysis has Σν = +1 (ATP → ADP + Pi), so c0 does not cancel. The stored part per cycle is
    RT (Σν μ°/RT − ln c0) = `transporter_drive0_J_mol` − RT ln `transporter_c0_mM` **(code: the
    layout's names)**.
  - It is not the kernel's Δ_rG'° at 1 M, which adds RT ln(1000 mM / c0). Nor is it R-fuel's
    −30.5 kJ/mol, which is at 1 M. The two differ by RT ln 1000 per cycle.
- **Material:** the role `produced` records ATP −cycles, ADP +cycles and Pi +cycles. It is
  charge-neutral, so the global ledger `total` closes. Without it, `total` fails by exactly that
  record (the core's (m) finding).
- **Heat:** −cycles × ΔG_cyc ≥ 0, as today. There is no work, since the free energy comes from the
  stored rows.
- **Near zero ATP:** the kernel's rational form is already written. ATP falls to about 1.7e-4 mM
  in R-fuel's window.
- **Refusals kept:** a fuel row without a registry potential, and a held row any other mover
  writes (held fuel only).
- **§5.2's refusal, made fail-closed.** Today only the proton law refuses finite fuel. Once the
  gap's refusal is lifted, a neutral finite-fuel pump beside FR-4's protons would be admitted. So
  version 1 refuses finite fuel in any world with a dynamic proton row. That is any proton row
  that a declared kind names: the buffer's (`cells.rapid_proton_buffer@1`), a proton law's role,
  or the proton leak's row. Its test is FR-4's world with a neutral finite-fuel pump added.

### 17.3 What the code shows for R-fuel's world

1. **It composes (code).** D152 refuses a reacting species with a membrane, junction or channel
   route of @3's (`species_common.check_impermeant`). A kind's node moves are none of those, so
   ATP, ADP and Pi can be both regenerated and pumped. D152 runs as Strang halves around @3's
   step, and the pump runs inside it. The schedule m(t) is D152's own `reaction_controls`, which
   change on the clock's grid (D283).
2. **One authority for potentials: a gap (code).**
   - The pump reads μ°'/RT from the species registry (`species_registry.standard_potential`).
   - D152 parses its own `standard_mu_RT` and `standard_concentration_mM` per species and never
     reads the registry.
   - Only `cells.proton_buffer` and the transporter call `standard_potential`.

   So in R-fuel two declarations would carry ATP's, ADP's and Pi's potentials, and nothing checks
   that they agree. F2 asks for one authority (ruling D3).
3. **Y's leak is tableau-booked (code).** Y has two movers on one patch: the pump and the leak.
   `passive_routes._exact` drops a route that shares a row with a non-passive mover, so the leak
   keeps the tableau's booking of its dissipation, not §7.5's exact one. This answers
   transporter/PLAN.md §6's open question. The leak's heat is then second order in dt, like
   every tableau-booked route's.
4. **The neutral transporter on a bounding patch is open (code).**
   - CLOSED_COMPARTMENT_DESIGN §3.4.1 admits it, but records it as open: it has no `bound_rate`
     and no stage term. `transporter.bound_rate` covers the proton law only.
   - Near its static head, its material slope at the outside node is about k S n e^a / n_out,
     which grows as the store empties.
   - R-fuel would be its first consumer (ruling D4).
5. **The step does not bind at milliseconds (S).** transporter/PLAN.md's "0.1 ms or finer" read
   k_f as the rate; D152's condition is dt·L ≤ 1 on each unidirectional flux.
   - The regeneration's largest L is k_f a_D a_Pi: 0.9 s⁻¹ at the start, about 1.8 s⁻¹ when Pi
     reaches 6 mM. Its reverse flux is about 4e-4 s⁻¹.
   - The pump's slope at the store is about k n / n_Y,s ≈ 0.02 s⁻¹ (n_Y,s ≈ 6 fmol).
   - The leak's L = 1e15 P A (1/V_c + 1/V_s) ≈ 0.012 s⁻¹.
   - The world has no charged row, so no electrical stiffness.
   - The step is therefore set by accuracy. The recovery's time constant is about 1 s, so the
     error is about (dt/1 s)²: 1e-6 at 1 ms and 1e-4 at 10 ms, against the 1e-3 budget (S). A probe
     measures this before the ladder is declared (ruling D5).

### 17.4 Acceptance, from transporter/PLAN.md §4 (kept, with the corrections above)

- **The runs:** R-fuel's calibrated world, with three runs.
  1. **Finite fuel, depletion and recovery.** J_cyc and ATP at 99 and 299 s; ADP and Pi at 299 s;
     Δ_rG'_ATP; Y in the store at 99, 299 and 900 s; recovery within 1% by 302 s and 0.1% by 303 s;
     cycles and regenerated material; the three heats; W = 0; moiety drift; the energy ledger.
  2. **Held fuel.** Nothing depletes, and W is the maintenance's work.
  3. **The control, m ≡ 1.** Its effect is at least 10 × the budget (G3).
- **Budgets:** 1e-3 relative, as FR-4's J3 and J4. R-fuel's floor resolves this: ATP within
  6.3e-14 mM and J_cyc within 4.3e-16 fmol/s.
- **Planted errors**, each of which must be caught:
  - the stored rate omitted: the observation's residual is exactly minus the stored part's rate,
    in §17.2's 1 mM frame, at a test c0 other than 1 mM, so a missing ln c0 would show;
  - `produced` omitted: `total` fails by the record;
  - a fuel stoichiometry off by one: the moiety check;
  - the regeneration's potentials declared unlike the registry's: D3's check, under its option
    (a).
- **The record:** a third protocol beside FR-4's and FR-5's (generic name `finite-fuel-v1`),
  drafted, rehearsed and registered as theirs are. It uses the same generator and judge.

### 17.5 The decisions, each with its cost and a recommendation, and the rulings

- **D1. The first finite-fuel world.**
  - (a) R-fuel's neutral pump (D176 item 2, as planned).
  - (b) FR-4's proton pump on finite fuel. That needs §5.2's explicit-proton boundary: charged
    reactions (§11 row 4, not started) and untransformed hydrolysis protons, weeks of work.

  **Recommended: (a).** (b) follows later, on the same kind path.
- **D2. Where R-fuel's store lives.**
  - (a) As FR-1's owned compartment inside the cell, the reference's own geometry (a 2.5 µm store
    in a 5 µm cell). It exercises the compartment with a pump on its bounding patch, as FR-4 does.
  - (b) As a finite outside node, with no compartment operator. That is simpler, but the
    small-node question of §17.3 item 4 stays the same.

  **Recommended: (a).**
- **D3. One authority for ATP's, ADP's and Pi's potentials** (§17.3 item 2).
  - (a) A binding check that refuses a world where D152's declared μ°/RT for a species differs
    from the registry's, converted to one c0. It is small, about 0.25 agent-day, and the
    operators' or the core's file.
  - (b) D152 reads the registry's potentials and drops its own. That is larger, since D152's
    declaration format changes.
  - (c) No check. That falls short of F2's one authority.

  **Recommended: (a) now, (b) later.**
- **D4. The neutral transporter's material bound at a small node** (§17.3 item 4).
  - (a) A per-stage material-rate refusal for the neutral law, at both of its nodes, in the kind's
    own hooks. This is general, and it closes §3.4.1's open item. Whether a kind's hook can see
    dt is a question for the core (§17.7).
  - (b) Measurement only: R-fuel's pump slope is about 2e-5 of 1/dt at 1 ms (S). That is cheap
    now, but it leaves the item open for the next, faster consumer.

  **Recommended: (a)**, if the core confirms a seam; otherwise (b), with the item kept open.
- **D5. The dt ladder.** PLAN's criteria (2, 1, 0.5 and 0.25 ms; 6.75e6 steps, about 2.5 CPU-h)
  were written before any code.
  - (a) Keep them.
  - (b) Run a probe first, at 1 and 10 ms over 900 s (S: a few CPU-minutes). Then a dated pre-run
    correction would declare the ladder; for example 8, 4, 2 and 1 ms costs about 0.6 CPU-h.

  **Recommended: (b).** Either way the criteria stay fixed before any judged run.

**Ruled by the lead, 16 November 2026** (within D176 item 2, which was already planned):
- **D1: (a).** R-fuel's neutral pump comes first. The proton pump on finite fuel follows later, on
  the same kind path.
- **D2: (a).** The store is FR-1's owned compartment.
- **D3: (a) now, fail-closed; (b) later.**
  - The evidence includes every registered world still parsing under the check.
  - First, main is searched for any world that declares one species' potential both through
    D152's `standard_mu_RT` and through the registry, so the check cannot newly refuse an existing
    world unannounced. **Searched 16 November on main 7c8bfa47 (code): none.**
    - D152's worlds are built in `tests/unit/test_species_reactions*.py`,
      `validation/tissue/species_reactions_fixtures.py` and `_crossrev.py`, and one protocol
      (`mg0c_turing_v1.json`). None declares the inner model's registry potentials.
    - The registry's worlds are in `test_species_registry*.py`, `test_transporter_kind.py`,
      `test_proton_buffer_kind.py`, `test_fr45_damage_and_worlds.py` and
      `validation/compartment_ph_engine/definitions.py`. None declares D152's operator.
    - No JSON world on disk declares both. The older calcium family's `standard_mu_RT` belongs to
      its own reaction networks (`legacy/core/reaction_spec.py`), not to either.
  - The check's location waits on the core's answer (§17.7 question 2).
- **D4:** (a) if the core confirms a seam, otherwise (b), with the item kept open. This waits on
  the core's answer (§17.7 question 1).
- **D5: (b).** The probe runs at 1 and 10 ms first. Then a dated pre-run correction declares the
  ladder, and the criteria stay fixed before any judged run.

### 17.6 Who does what, and the cost (agent-days, S)

- **FR45 (this lane):**
  - the kind's finite-fuel path, its tests and planted errors: 0.5–1;
  - R-fuel's engine world, records, generator parts and protocol draft: 1;
  - the probe, the dt study and the rehearsal on CPU: about 1–3 CPU-h.
- **The operators' or the core's owner:** D3's check, about 0.25, and D4's seam question.

### 17.7 Questions for the core

1. **D4's seam:** can a kind refuse a stage on a material slope that depends on dt, or should the
   per-stage material rule gain a kind term, as B7's charge rule did (`stage_term`)?
2. **D3's check:** in `species_registry.check_definition`, or in D152's parse?
3. **The energy observation:** under (m), with D152's standard term booked per half-step and the
   pump's stored rate in-step, is `energy_balance_pJ_s` expected to close at rounding in a world
   where both write the fuel rows? This lane's probe will measure it either way.

**The core's answers (16 November 2026, relayed by the lead):**
1. **D4: (a), go.**
   - The core builds a kind hook, `material_term(read, potentials, control, p, *, xp)`. It returns
     the kind's material slope (1/s) on [cells, then outside nodes].
   - @3's checked step refuses when dt × max(slope) > `EXPLICIT_STEP_BOUND`, beside B7's rule.
   - No program changes until a kind declares the hook.
   - This lane adds the neutral transporter's term, which closes CLOSED_COMPARTMENT_DESIGN
     §3.4.1's open item.
2. **D3:** the check lives in `species_registry` as `check_potentials`, called from
   `check_definition`. A contract hook, `species_potentials(declaration)`, is implemented by D152.
   The core builds both.
3. **The observation closes at rounding.**
   - D152 is not part of it, since its in-step rates are zero.
   - With `stored_pJ_s` the pump's terms cancel exactly. Leaving it out leaves minus the stored
     part's rate, as §17.4's planted error expects, in §17.2's frame.
   - D152's standard term matters for the integrated energy ledger instead, which is why D3's
     check is the guard of record.

## Appendix A. Equations for the independent references

Write these from this appendix alone. The state per node is the amounts. Everything else is
algebraic.
- **Nodes:**
  - c, the owner cytosol: volume V_c;
  - L, the lumped lumen: volume V_L, patch area A_b, capacitance C_b;
  - the held bath, at φ = 0, joined to c by an impermeant plasma patch of capacitance C_p.
- **States:**
  - H_eq,c, H_eq,L, and B_tot,c, B_tot,L (constant);
  - n_K, n_Cl and n_Na at c and L;
  - n_X at c and L (FR-5);
  - d (FR-5).
  - Fuel concentrations are constant (held).
- **Algebraic quantities:**
  - h_c, h_L from §4.1, with V = V_c or V_L;
  - q_L = F × 1e-15 × (fixed_L + H_eq,L − B_tot,L + n_K,L + n_Na,L − n_Cl,L) for B_L's base
    valence −1, and likewise q_c with B_c;
  - initial H_eq and fixed charges as in §13: H_eq = V (h₀ + B̄ h₀/(h₀ + K)), and fixed set so
    each node starts with q = 0;
  - V_b = −q_L/C_b;
  - φ_c = (q_c + q_L)/C_p, which stays 0 here.
- **Fluxes,** positive from c to L, in fmol/s. P A c gives mol/s, with P in m/s, A in m² and c in
  mol/m³ (= mM); multiply by 1e15 for fmol/s.
  - counterion s: J_s from §7.1 with u = z_s F V_b/(RT);
  - proton leak: J_H from §7.1 with c_in = h_c, c_out = h_L and z = 1, times (1 + d P_pore,H/P_H)
    in FR-5;
  - pump: J_cyc from §6 (cycles), contributing +n J_cyc to L's H_eq;
  - cargo: J_X = (f(pH_L) P_X + d P_pore,X) A_b (c_X,c − c_X,L) × 1e15;
  - damage: §9.
- **Equations:**
  - dH_eq,L/dt = n J_cyc + J_H;
  - dH_eq,c/dt = −(n J_cyc + J_H);
  - dn_s,L/dt = J_s and dn_s,c/dt = −J_s for each counterion and cargo.
- **Energy identity to check:**
  - ΔG_stored(t) + Q(t) = W(t), with W = ∫ (−Δ_rG'_ATP) J_cyc dt;
  - Q = ∫ [−ΔG_cyc J_cyc + Σ_routes J (μ̃_in − μ̃_out)] dt, with μ̃ from free concentrations and
    potentials;
  - G_stored = Σ_nodes [G*(node) + Σ_{s ∈ Na, K, Cl, X} n_s RT (ln(c_s/c°) − 1)] + ½ C_b V_b² +
    ½ C_p φ_c², with G* from §4.4 (free H⁺, HB_k and B_k at the closure's speciation).
  - The standard potentials of the ions cancel, because every route conserves each species. The
    fuel rows are held, so their stored energy is constant, and the maintenance's W carries
    hydrolysis.
- **Integration:** Radau, rtol 1e-11. Report at the engine's record times.

### A.2 The kinetic reference: full protonation kinetics

This is written so that the reference does not share the closure's assumption. It is the same
system with each buffer's protonation resolved, and its limit as k_on grows must be §A's closure
system.
- **States per node:** free n_H; for each buffer k, n_HB,k and n_B,k, with n_HB,k + n_B,k = B_tot,k
  conserved; the ions, cargo and d as in §A.
- **Each buffer's reaction** HB_k ⇌ H⁺ + B_k, in mM/s:

      r_k = k_off,k a_k − k_on,k h b_k,   k_off,k = k_on,k K_k,

  with h = n_H/V, a_k = n_HB,k/V, b_k = n_B,k/V, and K_k from the registry's potentials (§4.1).
- **The equations:**
  - dn_H/dt = V Σ_k r_k + (transport of free H⁺);
  - dn_HB,k/dt = −V r_k;
  - dn_B,k/dt = +V r_k.

  Transport acts on free H⁺: the pump's n J_cyc and the leak's J_H read h and V_b. Everything else
  is as in §A. The charge uses every form with its valence; q is unchanged by r_k.
- **The initial state:** the equilibrium speciation at the declared pH₀, so a_k = B̄_k h₀/(h₀ + K_k).
  This is the same start as the closure's H_eq.
- **What the references show:**
  - **convergence:** for k_on in {1e3, 1e5, 1e7} mM⁻¹ s⁻¹, the largest |pH_kinetic − pH_closure|
    over the run, falling as k_on grows. The closure is the limit;
  - **inside the envelope** (k_on ≥ 1e5 mM⁻¹ s⁻¹ in §13.1's world): within the 1e-3 pH budget;
  - **outside it** (k_on = 1e-3 mM⁻¹ s⁻¹): beyond the budget, so the comparison must fail (§4.2).
- **Integration:** Radau or BDF, rtol 1e-11. The kinetic system is stiff, at λ up to about
  4e8 s⁻¹.
- **Energy:** the reaction's heat −Σ_k ∫ V r_k Δ_rG_k dt ≥ 0 joins Q. In the limit it vanishes,
  matching the closure's zero buffering dissipation.
