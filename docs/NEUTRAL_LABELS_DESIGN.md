# Neutral arrival-time labels (FR-42): desk assessment

**Status: proposed, 22 November 2026, by the kinds owner, for the lead.** Desk only: no code was
written or run. The code was read at main 184fc81c. **S** marks this note's own reading or
proposal.

**The request** (FR-42 in [FEATURE_REQUESTS.md](FEATURE_REQUESTS.md); D288; erratum B,
[TEMPLATED_POLYMERISATION_LAWS.md](TEMPLATED_POLYMERISATION_LAWS.md) §9.8 and §9.13): a label never
changes the dynamics or the energy.
- Loss is computed once per physical population and shared by label as J n/N.
- Potentials, free energy and heat come from the physical population.
- A new cohort starts at zero.
- Windows count arrivals over [start, end).

## 0. Summary

| | |
| --- | --- |
| **Where a row's own potential enters** | In operators' laws: templated polymerisation's degradation factor, which changes the dynamics. In energy terms: turnover's and exchange's work, every face, route and patch heat (F2's exact face heat included), and @3's chemical free-energy term, which change the books |
| **So** | Neutrality needs a physical population that the energy ledger reads, not operator-by-operator fixes. @3's chemical term and every heat booking sum over a species' rows |
| **Two-sided routes** | Split each one-way flux by its source's shares. For Fick faces and constant-field routes the one-way parts are the law's own two terms. A charged logmean face has none, so it needs a declared one-way form |
| **A cohort at zero** | Possible only if shares are not stored amounts. The physical row stays positive and its shares may be 0 |
| **Recommended** | (A) Labels as share vectors on a physical row: operators and @3 compute on totals, and each one-way flux carries its source's shares. Staged: pools first (FR-38's consumer), then transport |
| **What moves** | No registered world. D1's and FR-33's examples move their booked heat, not their material. FR-38's class rows move about 1e-8 at R1 (development) |
| **Price** | A: 7–10 agent-days in stages, gates included. B, a registry population of sub-rows read by total: 11–15 |

## 1. Where a row's own potential enters today

**(a) In the operators' own laws** (these decide the dynamics):
- **Templated polymerisation's degradation:** J_D = k n (1 − e^y), with y from the polymer row's
  own μ (operators/templated_polymerisation.py, `j_deg`). Each class row reads its own
  concentration, so its factor is 1 − e^(y_f) (N/n_k)^(1/L) (erratum B). **The dynamics change**
  with the number of classes.
- **Turnover's flux** is first-order, k n, and exchange's likewise. The rate reads no potential,
  so **the dynamics are neutral**.
- **@3's faces** (logmean_electrodiffusion@1): for an uncharged row the flux is factor (a − b),
  linear in each row, so **neutral** (D1). A charged row's drift carries L(a, b), which is not
  additive, so **not neutral** (the Lean lane: 72.82% at +10 mV).
- **Patch and junction routes** (constant_field@1, GHK at the shared voltage): linear in each row,
  so **neutral**.

**(b) In the energy terms** (these decide the books, and they are global):
- **@3's chemical free-energy rate,** `1e-3 RT Σ ln(c) × rate` per species row
  (models/surface_pump_v3.py, `chemical = ...`). Each row's own ln c enters. Split rows carry a
  mixing term Σ n_k RT ln n_k that the physical population does not.
- **Turnover's work:** the exact free-energy change of the touched node per row
  (`adapter.species_chemical_free_energy_pJ(n, moved, ...)`), and **exchange's** likewise.
- **Face heat:** the tableau's J RT ln(a/b) per row, and F2's exact_free_energy_heat@1 per row's
  exact decrease. Opposing label gradients book heat where the unsplit species books none (the
  Lean lane's D1 finding). **Route heat** (passive routes' exact booking) is per row too.

**So (S):** neutrality cannot be reached operator by operator. Fixing templated polymerisation's
factor alone would fix the dynamics but not the books. @3's chemical term and every heat booking
sum over species rows, so each must sum over the physical population instead. That needs a
registry-level notion of the physical population that @3, every operator and the energy ledger
read. D1's families declare the grouping, but nothing reads them as one population.

## 2. The share rule on two-sided routes

**Rule (S):** compute each one-way flux on the physical totals, then split it by its source
population's shares. A forward flux carries the source node's shares, and a backward flux the other
end's. New material from a backward chemical flux joins the label the window names. Splitting the
net flux would give FR-33's transfer at equal totals no label movement, since the net is zero while
labelled material crosses one way and unlabelled the other.

| Law | Its one-way parts | Share split |
| --- | --- | --- |
| Fick face (uncharged logmean) | factor a and factor b | J+ s_a, J− s_b. Equals the per-row flux exactly, since the law is linear |
| Constant-field route (GHK) | P A x/(1 − e^(−x)) a and P A x e^(−x)/(1 − e^(−x)) b | Same, at the shared voltage |
| Charged logmean face | None: L(a, b) μ/RT has no one-way form | Needs a declared one-way decomposition, or is refused |
| Reversible mass action (local_species_reactions@1) | k+ Π reactants, k− Π products | Each by its own side's shares |
| Templated polymerisation's degradation | k n (forward), k n e^y (backward, re-synthesis) | Forward by the polymer's shares. Backward joins the window's arrival label |
| Turnover, exchange | One-way already | By the source's shares |

## 3. A cohort that starts at zero

The engine refuses a non-positive stored amount at any active node: @3's domain at every checked
state, and since the guard (6f3aa8f2), the binding closure's held totals at every stage. So a label
**row** cannot start at zero. D1's rows and FR-38's class rows start at the inventory trace, which
FR-42 forbids.

**Shares can be zero (S)** if they are not stored amounts:
- the physical row stays positive, and the domain checks only it;
- a share vector s_k ∈ [0, 1] per node with Σ s_k = 1 carries the labels;
- a new cohort's share is exactly 0 at its window's start, and grows by its arrivals.

The domain then checks the shares by value: finite, each in [0, 1], and summing to 1 within
rounding.

## 4. What moves

- **Registered worlds: none.** No registered world declares a family or class rows, and with
  static switches the undeclared programs are unchanged.
- **D1-labelled worlds and FR-33's examples** (the first test, the synapse acceptance, the
  two-node control):
  - their material and transfer records stay the same, since the laws are linear;
  - their booked face heat changes, to the physical population's value. That resolves D1's
    docstring caveat;
  - **F2's trace start** becomes an exact zero start.
  - The host tracer (FR-33's one-way pulse-chase) is unaffected.
- **FR-38's class rows** are replaced by shares (D288). The 1 − e^(y_f) (N/n_k)^(1/L) departure
  vanishes: about 1e-8 relative at R1 (erratum B), and up to percent level near the domain bound.
  Route 1's blank subtraction is no longer needed. Route 2, cohort.py, stays as the host-side
  check.

## 5. The design options

**A. Labels as share vectors on a physical row (recommended, S).**
- **The declaration:** the registry declares a species' labels, a list of IDs. @3's state gains
  `label_share` [label, node] for that species, only where declared (a static switch, as K4's
  readouts do).
- **Dynamics:** every law computes on the physical row's total, as today, so the dynamics are
  unchanged by construction.
- **Shares:** each step updates the shares from the step's one-way fluxes (§2). Each mover reports
  its one-way parts for a labelled species, a contract addition for operators and kinds. @3's
  faces and routes report theirs from their own two terms.
- **Energy:** the physical row only. Nothing reads a share, so free energy and heat are unchanged.
- **D148, crossrev and G1:** unchanged for every world without labels.
- **Checkpoints:** the new field appears only where declared, so a checkpoint version for labelled
  worlds only.
- **Price, staged:**
  - Stage 1, pools: the registry's labels; @3's share state; turnover's and templated
    polymerisation's one-way reports; windows by step index (as FR-33's step_index); FR-42's
    checks 1 to 3 in one pool. **3–4 days.**
  - Stage 2, transport: faces and routes report one-way parts; the charged logmean face refused
    without a declared decomposition; FR-33's first test rebuilt on shares. **2–3 days.**
  - Stage 3: exchange, reactions and kinds' one-way reports, each by its owner. **1–2 days.**
  - Gates: about 1 day.
  - **A in all: 7–10 agent-days.**

**B. A registry-level population with labelled sub-rows that every law reads by total.**
- Each sub-row stays a stored species row.
- Every law, @3's chemical term and every booking read the family total for rates and potentials,
  and split their moves by sub-row shares.
- The positivity domain must exempt sub-rows, so that zero is allowed.
- It touches every law's read path, @3's field and energy terms, and the binding closure.
- D148: every family world's records move; registered worlds stay unchanged.
- **Price: 11–15 agent-days,** across every owner.

**C. Host-side only** (cohort.py's method generalised: the run's per-molecule loss J/N and the
arrival history).
- Exact for a well-mixed pool under any loss law, so FR-42's reference case passes on the host.
- It cannot follow labels through two-way transport, since @3's records are net.
- **Price: 2–3 days,** and it leaves FR-33's transfer case unserved.

**Recommendation (S): A, staged.** Stage 1 serves FR-38's rebuild (D288). Stage 2 serves FR-33's
transfer. C remains the host-side cross-check, as route 2 is for FR-38.

## 6. The requester's acceptance checks, and how each would be built

1. **Unlabelled and 1, 2 and several labels from one initial state,** including unequal shares, an
   empty label and a state near the edge of the supported concentration range.
   - Under A the physical fields are identical bit for bit across label counts, since no law reads
     a share. The check compares every physical state field and the energy ledger's records
     between K = 0 and each K, exactly.
   - At every comparison time the shares sum to the reference total.
   - The edge case: templated polymerisation's degradation near y → x_dom, where the class rows
     departed by percent.
2. **Arrivals at a window's start and at its end, with older material present.**
   - The window resolves to step indices (FR-33's step_index). Production in the step that starts
     at the window's start joins the cohort; the step that starts at the end does not.
   - Survivors are checked against an independent calculation: the arrival history times
     exp(−∫ J/N dt), from the run's own per-molecule loss, as cohort.py does.
3. **Two physical populations with different loss laws, one labelled.**
   - Each keeps its own reference trajectory, bitwise against its unlabelled run.
   - The labelled one's shares account for all its material at every time.

**The reference case, dN/dt = −N².** Of today's laws, a second-order loss is mass action
(2A → B in local_species_reactions@1, with B removed or held). So stage 1's acceptance needs either
that law with one-way reports, or a test-only law. N(t) = a/(1 + a t): the new cohort is 1/4 of
3/4 at t = 1, against blank subtraction's 1/12.
