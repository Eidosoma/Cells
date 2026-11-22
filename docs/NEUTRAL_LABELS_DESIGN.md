# Neutral arrival-time labels (FR-42): desk assessment

**Status: option A chosen (D289); stage 1 built (§7), 22 November 2026, by the kinds owner.**
Sections 0 to 6 are the desk assessment, written before any code at main 184fc81c. **S** marks
this note's own reading or proposal.

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

## 7. Stage 1 as built (pools)

**The operator.** Labels are an operator, `neutral_arrival_labels@1` (operators/species_labels.py),
not a registry key (the lead's approval). The registry is host side only, and the share state, each
step's arrival label and the update reach the traced program. A composition's types are keyed on
its law tuple, so a world without the operator keeps its composition key and its programs by
construction.
- **The declaration:** `species`, each with its `labels` (one to 16, distinct) and its `initial`
  shares by node, a list that may be empty.
- **The base** is each species' first label. It holds unlabelled material: all initial material
  at every node not listed, and every arrival outside a window. Unlabelled material counts as a
  share, as FR-42 asks.
- **The schedule:** `label_arrivals`, per species, gives the label that each step's arrivals join.
  - Switch times are exact multiples of dt, and each step's label is the one in force at its start.
  - Steps are resolved by step index with execution/grid.py's `same_instant`, the predicate D283
    names for label switches. So arrivals in the step that starts at a window's start join it,
    and those in the step that starts at its end do not.
  - `label_arrivals` is a new consumer of the on-grid rule, for D283's stage 2 to sweep.
- **The state:** `label_share` [labelled species, label, cell] and `label_outside_share` [...,
  outside node], padded labels at 0 under a presence mask. Checkpoints carry it, and a resume is
  bit for bit, in process and through a snapshot.
- **A diagnostic:** `label_closure_relative`, the largest closure residual of any reporter's
  half-step. It measures each reporter's own consistency. That no other mover touched the row is
  the refusals' to hold.

**The interface** (operators/contract.py, the lead's leave; one for every operator, agreed with the
gene regulation agent). A reporter's `half_step` takes `labels=(rows, arrival)` and returns
`(state, valid, moves)`, its state and validity bit for bit the unlabelled call's.
- **moves:** `(out [m, node], into [m, label, node], transfers)`, from the same combination as the
  booked move.
- **The node axis:** cells, then outside nodes. A reporter at cells only may give its cells alone.
- **transfers:** `()` until stage 2.
- **The composite** (models/pump_composite.py `_half_step`, the lead's leave) advances the shares
  after each applied half-step of a reporter. That covers the midpoint path's second half-step;
  its predictor runs unlabelled. Without a label owner no call changes.
- **The reporters:**
  - turnover: its booked clearance out, its production in;
  - reactions: each driven route's extent times its consumed and produced coefficients, with the
    lead's leave for species_reactions.py;
  - templated polymerisation: the gene regulation lane's side, 824da76b.

**The update** (numerics/label_shares.advance). Over one half-step it solves
n1 = n0 e^(−u) + I φ(u), φ(u) = (1 − e^(−u))/u, for u ≥ 0 from the engine's own n0, n1 and the
arrivals I, by bisection with a fixed count. Each label's material is then n0 s e^(−u) + into φ(u),
and the shares are that over its sum.
- **Non-negative for any step.** Zero stays zero until a label receives arrivals, so a new cohort
  starts at zero.
- **Exact for a constant per-molecule rate,** with constant arrival rates, within a half-step.
  Turnover is such a case.
- **Without arrivals the shares are kept bit for bit,** whatever the loss law. FR-42's reference,
  dN/dt = −N², is therefore exact: the new cohort is 1/4 of 3/4 at t = 1, where blank subtraction
  gives 1/12.
- **Otherwise second order.** With k(t) and a(t) varying within a half-step of length h, the new
  material it attributes exceeds the exact amount by (a(0) k′(0) − a′(0) k(0)) h³/12 + O(h⁴), and
  the old falls short by as much. That is second order over a run, as Strang splitting is.
  - A halving row measures this: per-halving ratios of 7.7 to 7.9, and the coefficient within 0.8%
    at h = 0.0125.
  - The error vanishes when a and k vary in proportion.
- **Never the totals:** they are the engine's, so no record of the physical state moves.

**How FR-42's check 2 is computed** (against the run's own per-molecule loss rate). The cohort's
survivors at T are the arrivals of its window's steps, each carried by exp(−∫ k dt) to T.
- Within each step, k = one-way loss / n, from the run's records.
- Where k is constant within each step (first-order clearance at a scheduled rate), that
  calculation and the update agree at rounding. The test row measures 8e-16 against the analytic
  solution, at both boundaries.
- Elsewhere they agree to the update's second order.

**Refused in stage 1** (fail closed; each refusal names the stage that lifts it):
- **Stage 2:** a labelled species moved inside the inner step, by a face, a route, a channel, a
  pump, a kind or an in-step process (registry `moved_in_step`). Rows refuse a face, a membrane
  and a junction route, and a transporter kind's moved role and finite fuel. Today's pumps hold
  their fuel as parameters, so no fuel row of theirs is moved.
- **Stage 3:** exchange on a labelled species, and a passive reaction route on a labelled row.
  The reactions refuse the second themselves.
- **No stage plans these yet:**
  - other operators that write species amounts in their split parts without reporting;
  - events that write amounts;
  - closers, retirers, and providers of the amount references, such as a bath schedule.
- **D1's families:** a world that declares them admits only turnover and declarations beside them
  (D1's own refusal), so the label owner never meets a family row and reads no family. Shares
  replace family rows.
- **The composition matrix** (docs/PUMP_COMPOSITE.md) marks the law-level refusals "d" and lists
  the data-level ones.
- **Not refused:** RK4 on the coupled path. It is vacuous, since a coupled RK4 composition already
  refuses every split-only part, so no reporter runs there.

**What moves: nothing.** Worlds without the operator keep their programs, which crossrev and G1
check in the gate. In labelled worlds every physical field, observation and diagnostic is the
unlabelled run's, bit for bit, in each test row.
- **FR-42's check 1 as rows:** five pools in one labelled run against one unlabelled run, not one
  run per label count. The pools are independent, so each is its own initial state labelled its
  own way.
- **D1's and FR-33's examples, before and after:** all 422 history and observation arrays of their
  five worlds are bit for bit main's, and so are their diagnostics.
- **Templated polymerisation's reports (824da76b),** checked in a scratch merge only:
  - every record is bit for bit the unlabelled run's;
  - the shares sum to 1 within 1.1e-16;
  - the closure is within 1e-16.
- **The reactions' rule:** a species on both sides of one route counts its net, so a catalytic
  copy is never relabelled. Stage 3's owners inherit that rule.

## 8. Stage 2 (transport), and pools and sources (D296): the label owner's side

**The inner step's report** is the @3 owner's side, to the rule the lead confirmed.
- Faces and routes report their one-way amounts over the step:
  - for an uncharged face, c a and c b;
  - for a constant-field route, the GHK terms.
- Under ARS222 and N2, those amounts are the trapezoid of the start and end fluxes, plus the O(dt³)
  gap to the booked net, added to the side whose sign it has. So forward − backward equals the
  booked net at rounding, both are ≥ 0, and both are second order.
- Under the Euler IMEX, the stage terms are combined directly. RK4 refuses labels.

**The transfer update** (numerics/label_shares.advance_transfers).
- Each node is advanced by stage 1's kernel. Its arrivals carry their sources' shares: first at the
  step's start (predictor), then at the mean of start and predicted end (corrector).
- **Order:** second order. Measured against the exact linear exchange of three nodes, the error
  falls 3.9 to 4.0 times per halving.
- **Domain:** non-negative, and the shares sum to 1.
- **Exactness:** exact, at rounding, where no source's shares change.

**The composite** (models/pump_composite.py `_labelled_inner`). Where the inner step takes
`labels=` (static, by its signature) and the tableau is IMEX, the inner step returns its transfers,
and the owner advances the shares from them. Without a label owner, or before @3's side lands,
today's call is unchanged.

**What stage 2 admits.** Where the inner step reports, it admits:
- an uncharged face;
- a membrane route and a junction route (constant_field@1).

Refused, each naming why:
- a charged face, which has no one-way form;
- channels, pumps and operators' in-step processes;
- kinds, which wait for their hook after @3's side;
- RK4 beside any followed mover.

**Measured against exact rows** (tests/unit/test_neutral_labels_transport.py; @3's side
ac9f03e7, merged).
- **The method:** each case runs plain rows of the same material in the same world. Transport is
  linear in each row, so those rows are the exact reference.
- **FR-33's first test, rebuilt on shares** (validation/regions/example.first_test):
  - **Transfer:** the shares follow D1's P_L within 5.4e-7 of the label's scale, and 1.4e-7 at half
    the step: 4.0 per halving, second order. The label summed over the two regions holds at
    rounding.
  - **Local loss:** the shares and the cleared label match at rounding.
- **Routes:** a junction and two membrane routes carry the shares within the same bound.
- **Inner reporting** stays off beside declared kinds: @3's step refuses `labels` there until the
  kinds' hook lands.

**Pools and sources** (D296, operators/contract.py).
- **Reporter flags:** a reporter flags `LABEL_POOLS` or `LABEL_SOURCES` (static). It declares its
  pools, `label_pools`, entries of its own state holding a labelled species' material (the
  release hold), and its sources, `label_sources` (its chains).
- **Sources:** the owner's schedule may name a source. Each step a source reporter receives its
  sources' arrival labels, `source_arrival`. A source without its own switch takes its species'
  window.
- **Pools:** a pool reporter returns a pools part:
  - its pools' start and end amounts;
  - new material into them by label;
  - their losses;
  - `carried`, material that keeps its labels between sites, row sites (j N + k) and its pool
    entries.
- **The owner holds** `label_pool_share` [pool reporter, label, pool entry]. It advances a pool
  reporter's rows and pools together as sites, through the same predictor-corrector. A site with
  no move keeps its shares bit for bit, and the closure diagnostic covers both.
- **Limits:** labels may number up to 64 per species (producer × window). The domain's allowance is
  128 ulps.
- **Rows** (NumPy, no world):
  - a release carries the hold's shares;
  - a completion enters the hold at its label;
  - with no release the row keeps its shares bit for bit;
  - each source takes its own schedule, or its species' window.

**Replacement** (D284 and D296; the lead's leave for a minimal hunk in replacement@1's file).
- **The event reports what it replaced.** replacement@1's event takes `labels=rows` and also
  returns the slots it replaced. Its state and validity are bit for bit the unlabelled call's.
- **The owner relabels each replaced slot:** its labelled shares become the label in force for the
  species at the event step, the newcomer label.
  - The departing material leaves with its own shares.
  - A donor copy's material is newcomer material too. It does not inherit the donor's shares.
- **Producer identity across generations:** a source's schedule may switch its label at the event
  time.
- **Still refused:** replacement@2 (its event does not report). So is a template that would make a
  labelled species membrane-permeable, which replacement@1's own check already refuses as a new
  leak.
- **The composition matrix** admits replacement@1 beside the owner.

**What moves.** Worlds without the owner: nothing. Labelled worlds: the owner gains
`label_pool_share` and the control `label_source_arrival`, both empty where no reporter declares
pools or sources. So a stage-1 labelled checkpoint (development; none registered) does not
resume across this change.

## 9. Stage 3: exchange and the reactions' passive routes (the lead's leaves)

**Exchange** (scheduled_species_exchange@1).
- Its half-step sums each route's amount moved over its palindrome, stage by stage. It reports that
  sum as a transfer from the route's source to its destination: an export from the cell to its
  outside node, an import back. The transfer carries the source's shares.
- The owner advances such a reporter on the combined node axis, as it does the inner step
  (`advance_nodes`).

**The reactions' passive routes** (local_species_reactions@1).
- Each route's forward and reverse extents are the SSPRK(3,3) combination of its stages' one-way
  rates, combined as its extent is from its net rates. A driven route's are its extent and 0,
  bitwise as before. A passive route's are its two unidirectional fluxes.
- The forward extent consumes max(−ν, 0) and makes max(ν, 0), the reverse the opposite. So a species
  on both sides of a route counts its net in each direction.
- Chemistry makes new molecules, so products join their species' arrival label. A passive route's
  reverse flux re-makes its reactants at theirs.
- The refusal of a passive route on a labelled row is gone.

**What stays the same:** with labels, both operators' states and validity are bit for bit the
unlabelled calls'. Without labels nothing of theirs is traced. The owner's closure diagnostic reads
rounding for both.

**Kinds** (transporters, passive-route kinds) report after the @3 owner's stage hook lands.

## 10. D1's label families retired (D300)

The user's direction: D1's families, separate rows with their own potentials, are removed rather
than kept beside shares. "We don't want old backwards compatibility — we're still in heavy dev, not
even at alpha."

**Removed:**
- **The species registry's families:** the `label_families` key, `Family`, `family_of`,
  `family_rows` and `check_families`, with its operator check and the row-linear constants. The
  labels owner names the reported movers' laws itself.
- **The region export's family path:** summed rows, `host_transport`, and the hosts' records.

**Replaced:**
- **FR-33's examples run on shares:** the first test, and the synapse acceptance. Plain rows of the
  same material ride beside as the exact reference.
- **The readouts read a label's amounts from the shares** (`readouts.label_nodes`), and classify the
  owner as moving no amount.

**No registered world declared a family:** no definition in the repository names `label_families`.
