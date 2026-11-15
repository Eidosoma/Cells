# Compartment pH and state-conditioned transfer: FR-4 and FR-5 (design)

**Status: proposed (D142).** Written 15 November 2026 by the FR-4/FR-5 physics owner (D176), on
branch `fr45-physics` from tag `d172-base-2026-11-15`. It is design before code.
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
2. **Buffering is a rapid-buffer closure, not kinetic reactions** (§4).
   - Protonation relaxes at about 10⁸ s⁻¹ (**S**), so explicit kinetics are impossible.
   - A split implicit block would let the transport step move the free pool by several times its
     own size per step: a 250 nm lumen at pH 7.4 holds about 1.6 free protons (CP4).
   - The closure is the exact fast limit, conserves material and charge exactly, and is the
     organelle-pH literature's own treatment. It is declared as a reduced representation (D175).
3. **Counterions are explicit rows on explicit routes,** Cl⁻ in or K⁺ out, chosen by the world.
   Without one the pump charges the patch and stalls; that is the negative control.
4. **The charged patch needs an implicit route for a practical step** (the charged-patch test,
   §7.2). @3's energy ledger, not stability, sets the explicit limit, at dt × G/C_b ≲ 0.1.
   - Lysosomal Cl⁻ needs 0.05 ms explicitly (about 18 CPU-hours per 900 s); FR-5's pores need
     about 0.5 µs.
   - A counterion whose G/C_b ≤ 0.1/dt runs explicitly. For K⁺ at 140 mM on both sides and
     dt = 1 ms, that means P_K ≤ 2e-7 cm/s (**S**), which still carries the pump's current at a
     few mV.
   - That is FR-4's first world, with the face-free bound term, while FR-1's door 2 (the implicit
     patch) is built.
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
9. **The first worlds fit the species cap.** FR-4 needs 8 rows, FR-5 9, against 16.

## 1. Scope, representation and claims

- **Entity:** FR-1's owned compartment, a face-free finite node bounded by one patch whose inside is
  the owner's cytosol. Its identity comes from `compartments.identity_map`.
- **Representation, declared per world (D174, D175):**
  - continuum amounts;
  - either a single compartment, or a lumped population of N identical compartments as one node,
    with N × volume, area, capacitance and transporter capacity.
  - Lumping is exact for identical members, because V/A and C/A are kept (FR-1 §1.3). The claim is
    then a population mean.
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

For buffer k at one node, with acid dissociation constant K_k in mM (pK_k = −log₁₀(K_k/c°)):
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
- **where it is qualified:** k_on B̄ ≫ 1/dt and ≫ every per-free-proton transport rate (J/n_free),
  checked as declared bounds. Its error budget is set against the kinetic reference (§14).

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
  module (`processes/rapid_proton_buffer.py`, with neutral naming).
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
- **The rate**, in the Na/K law's form (`processes/kinetic_pump.py`):

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

- **Nothing was refused in advance:** @3's bound sees G/(C_p + C_b), and every failure was an honest
  run-time refusal.
- **The explicit limit is @3's energy ledger at dt × G_slope/C_b ≲ 0.1,** not stability.
  G/C_b = P F² c/(RT c_m) is independent of size.
- **Cost:** 3.6 ms per step in this 3-node world. So a 900 s FR-4 world with lysosomal Cl⁻ costs
  about 18 CPU-hours explicitly (**S**).

**The route, in order:**
1. **Now, for FR-4's first world:** a counterion with dt × G/C_b ≤ 0.1.
   - At dt = 1 ms and K⁺ at 140 mM on both sides, that is P_K ≤ 2e-7 cm/s. The world in §13 uses
     1e-7 cm/s, so dt × G/C_b = 0.051.
   - A 900 s world is then 9e5 steps, about 0.9 CPU-hours at the measured cost (**S**).
   - The face-free bound term B7 is added to `explicit_rate_bound` and `membrane_rate` as
     max over free face-free nodes of Σ_m G_m/C_node.
   - The bound is set by the energy threshold 0.1, not by stability, so that such a world is
     refused in advance rather than at run time.
2. **The implicit patch,** FR-1's door 2: a compartment's bounding-patch electrodiffusion joins the
   implicit part of the IMEX step, as face drift does.
   - It is local: a face-free node couples only to its owner. One node and one patch per
     compartment.
   - It is a new solver ID (D147), with its own qualification. The field-solver interface owns the
     factor and solve (FIELD_SOLVER_INTERFACE_DESIGN §6; INNER §13.4).
   - Cl⁻ counterions at lysosomal values, and every ionic pore of FR-5, wait for it.

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
- **The routing door** (D156's, door S §6) carries FR-5's control factors to the transfer and leak
  laws' rate multipliers: the damage d, and the pH factor f(pH_C).
  - The factors are evaluated on each stage's state where the routing door supports stage reads
    (INNER §7.2, B4).
  - Otherwise they are evaluated at the split, which makes the coupling first order in dt. The
    choice is declared, and the references use the stage form.

## 9. FR-5: damage, leak and reseal, and pH-conditioned transfer

- **Damage**, `prescribed_patch_injury_resealing@1` (unchanged equation, `processes/membrane_injury.py`),
  re-expressed as a control state on the bounding patch:

      dd/dt = k_inj u_inj(t) (1 − d) − k_res u_res(t) d,   d(0) = d₀ ∈ [0, 1].

  - u_inj and u_res are declared piecewise-constant schedules in [0, 1].
  - d is kinetic state with no ledger (FEATURE_REQUESTS, FR-5). Its role is continuous dynamical
    state.
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

| # | Refused today | Where | Owner and route |
| --- | --- | --- | --- |
| 1 | An ion route on the bounding patch (nonzero permeability or channel) | `compartments.py`, refusal 4 | **This note's owner** (`compartments.py`). Lifted for K⁺-class routes with B7 (§7.2, step 1); for Cl⁻ and pores with the implicit patch (step 2: the field-solver interface owner for the solve, this owner for the law's qualification) |
| 2 | A transporter (pump) on the bounding patch | `compartments.py`, refusal 4; there is no transporter kind | **This owner** (the pump law, §6, and the lifted refusal). B5's transporter kind and its insertion point in the inner step: **the core owner** (A1) |
| 3 | Reactions inside a compartment beside a bath dose | The whole-field `CONFLICTS_VIEW` | **The integration owner** (door S, A6). Neutral reactions at a compartment node are admitted today: `compartments.ADMITTED` lists D152, and D152 refuses only held-bath sites |
| 4 | Charged reactions | `species_common.parse_species` refuses nonzero valence | **This owner** (`species_reactions.py`, starting from `integration-d172` after the integration owner's declaration-only change). Version 2 admits closed charged reactions with Σ_s z_s ν_s = 0 exactly, in integers, for **slow** kinetics, and rewrites D150 §3's exact-zero charge argument. Buffering is not this route (§4) |

Two more, which this note adds:
- an @3 route for H at a buffered node (§4.3);
- finite fuel at a node with dynamic protons (§5.2).

## 12. Species budget against the cap of 16

| World | Rows | Count |
| --- | --- | --- |
| FR-4, first | Na, K, Cl, H, B (one buffer species: its totals differ by node), ATP, ADP, Pi | 8 |
| FR-4, with two buffer species | + B₂ | 9 |
| FR-5, first | FR-4's 8 + cargo X | 9 |

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
- **The cytosol:** Na 10, K 140, Cl 10 mM. Buffer B (base valence −1) with B_tot 50 mM, pK 7.2,
  starting at pH 7.2. Held fuel: ATP 3, ADP 0.3, Pi 3 mM. Δ_rG'° = −30.5 kJ/mol (a generic
  declared value). `transformed_at(7.2, pMg 3, δ 0.05)`.
- **The lumen:** Na 10, K 140, Cl 10 mM. Buffer B with B_tot 40 mM, pK 6.0, starting at pH 7.2
  (a resolved start). Mode `explicit`.
- **Fixed charges:** each node starts electroneutral, so q = 0 and V_b = 0.

### 13.1 FR-4: buffered acidification against a gradient

- **The patch:**
  - the pump: n = 2; k = 8.3027e-3 fmol cycles/s for the node (5,000 cycles/s per member × 1000
    members ÷ N_A × 10¹⁵); K_H 1e-4 mM, K_ATP 0.1 mM, a = 1;
  - the proton leak, P_H 6e-5 cm/s (6e-7 m/s);
  - the counterion K⁺ at 1e-7 cm/s (1e-9 m/s).
- **The run:** 900 s, explicit at dt = 1 ms (dt × G_K/C_b = 0.051), with B7.
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

- **The start:** FR-4's world at its steady state, a saved checkpoint and a declared start.
- **Cargo X** (valence 0) at 1 mM in the lumen and 1e-4 mM in the cytosol. That is a resolved
  start: the energy ledger refuses trace starts (SYN3A_MINIMAL_CELL_TRACK §5.2).
- **Transfer:** P_X 1e-8 m/s, f with pH₅₀ 5.5 and m 4.
- **Damage:**
  - k_inj 1 s⁻¹ on during [100, 110] s, then k_res 0.05 s⁻¹ from 110 s;
  - pore routes for H (P_pore 1e-6 m/s through the closure) and for X (1e-6 m/s).
  - Ionic pores are refused in version 1 (§9).
- **What it shows:**
  - X crosses while the lumen is acidic, and not when it is not;
  - damage opens a proton leak that raises the lumen's pH and releases X;
  - resealing lets the pump re-acidify;
  - every book closes.
- **Negative controls:** f ≡ 1 (no condition: X crosses at every pH); d ≡ 0 (no release burst).

## 14. Qualification, and what waits on whom

- **Numerical verification first,** against references written from Appendix A by a separate agent:
  - dt studies at second order;
  - the closure against a kinetic-buffer reference at k_on 1e10 M⁻¹ s⁻¹, solved by Radau. This is
    D175's reduction check, with its budget declared before the comparison and one case outside
    the envelope that must fail;
  - the passive contract for the proton leak (§7.1) on FR-1's closed pair. The Syn3A track's P0e
    found two closed topologies on main.
- **G1/G3 (D176):** exact contract tests per law (a NumPy ΔG per step), plus the scientific negative
  controls of §13, whose effects exceed the budget.
- **Waits:**
  - FR-4's code waits on B5's transporter kind (core owner), held rows and B3 (core owner), B7 (this
    owner, with the D148 round), and the identity map (FR-1's re-gate);
  - FR-5's code waits on FR-4, the routing door (D156's owner), and the injury law as a control
    state;
  - ionic pores and Cl⁻ counterions wait on the implicit patch.

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
  - q_L = F × 1e-15 × (fixed_L + H_eq,L − B_tot,L + n_K,L + n_Na,L − n_Cl,L) for B's base valence
    −1, and likewise q_c;
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
  - G_stored = Σ_nodes G*(node) + ½ C_b V_b² + ½ C_p φ_c².
- **Integration:** Radau, rtol 1e-11. Report at the engine's record times.
