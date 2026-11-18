# FR-6's A5″ references: a channel driven through a regulatory state with a per-cell prior

**Registered 18 November 2026, before any engine output exists.** These are the independent
references for A5″, the lead's ruling (c) on FR-6 (17–18 November 2026). A5″ is A5's channel
response (`docs/INVENTORY_COUPLING_DESIGN.md` §4.4) driven through a regulatory state, with a
per-cell prior: FR-6 item 3, "the same formulation given to differently conditioned cells".
- Two cells start with different s₀ and receive the same regulator dose.
- Each cell's K-leak population follows its own state.
- V and the amounts are judged against R-cell, with the state integrated alongside.

The worlds are registered here (the lead's ruling), and the FR lane builds its protocol on them
after FR-1 and FR-3. `REFERENCES_USAGE.md` is the interface.

**Scope, ruled:**
- FR-6 item 1 is qualified for gate-free populations by the judged A5 (15 November, 47 of 47).
  The lead records it.
- A5′, a gated population, comes later, if needed.
- The routing door (item 2) belongs to the core pass (seam B1, D216).
- The leak and pump targets are not built.

## What is reused, exactly

| Module | Reused for |
| --- | --- |
| `validation/coupling/cells_reference.py` (R-cell) | Unchanged: the world classes (`World`, `Cell`, `Patch`, `Population`, `Regulator`, `State`, `Input`, `Coupling`), `simulate` (Radau, rtol 1e-10, the state integrated with the ions as R-feedback does), `floor`, and its model's right-hand side for the stand-in |
| `validation/coupling/state_reference.py` (R-state) | Unchanged: `Turnover`, D150's regulator in closed form |
| `validation/coupling/piecewise_ode.py` | Unchanged, through `simulate` |

**New here:**
- the registered world (`worlds.py`, which writes `reference_inputs.json`);
- the reference wrapper and controls (`a5pp.py`);
- the honest second-order stand-in;
- the design and values (`design.py`, `designs/`).

## The registered world (`reference_inputs.json`, world `a5pp_prior`)

A5's judged world, extended to two cells.
- **Cells:** two identical pump-free cells, a and b. Each is 2 pL on one constant-field patch of
  4 pF (area 4e-10 m²), facing a bath held at 0 V. The leaks are Na 1e-10, K 2e-9 and Cl 5e-10
  m/s. The cytosol is Na 12, K 140 and Cl 30 mM, the bath Na 140, K 5 and Cl 145 mM, and both
  cells start at −60 mV.
- **Channel:** a gate-free K-leak population (`kleak_always_open@1`) of 2e-9 m/s in each cell.
- **Regulator:** X in each cell, held at 1 µM by D150's turnover (clearance 5/s) and driven toward
  10 µM over [0.2, 0.5) s. The dose is the same in both cells.
- **State:** s1 in both cells, read from X by a Hill activation (K 3 µM, n 2), with k_on 5/s and
  k_off 1/s. **s₀ = 0.1 in a and 0.8 in b.**
- **Coupling:** F = 0.1 + 0.9 s1 (`state_fraction`) on each cell's population.
- **Run:** 2 s, recorded every 50 ms, on the dt ladder 1, 0.5, 0.25 and 0.125 ms. Every segment
  start lies on the grid.

The values are synthetic, within A5's bracket.

## The registered design: claims, floor, controls and margins

- **The reference's floor** (`cells_reference.floor`: rtol 1e-10 against 1e-12): V 3.3e-14 V,
  amounts 1.4e-12 fmol, s 2.1e-14.
- **The honest stand-in** is the explicit half of ARS(2,2,2) on R-cell's own right-hand side. It
  errs by 6.6e-7, 1.6e-7, 4.0e-8 and 1.0e-8 V at the four rungs: order 2.03, 2.01, 2.01. It also
  errs by 2.1e-8 to 3.2e-10 fmol, and in s by 2.9e-6 to 4.6e-8. Every error stands far above the
  floor.
- **The controls**, as each one's largest deviation and its margin over the honest error at 1 ms
  (all in `margins_over_honest`, per rung):

| Control | V | amounts (fmol) | Margin at 1 ms (V) |
| --- | --- | --- | --- |
| s₀ swapped between the cells | 5.2 mV | 1.1e-3 | 7.8e3 |
| one s₀ for both (a's, b's) | 5.2 mV | 1.1e-3 | 7.8e3 |
| one s₀ for both (the mean) | 2.9 mV | 5.9e-4 | 4.3e3 |
| s₀ ignored (both 0) | 6.1 mV | 1.3e-3 | 9.2e3 |
| the state bypassed (A5's instantaneous Hill form) | 5.4 mV | 3.2e-3 | 8.2e3 |
| k_on 1% off | 2.4e-5 V | 1.7e-5 | 36 |
| k_off 1% off | 2.5e-5 V | 1.8e-5 | 38 |
| the basal level × (1 + 1e-3) | 1.0e-6 V | 5.0e-7 | 2 (amounts: 24) |

**The two cells are told apart.** A swapped, shared or ignored prior departs by thousands of times
the honest error at every rung, as the lead required.

**Zero power, or not shown:**
- A state reading the other cell's regulator: both cells receive the same dose, so X is equal in
  both. A dose that differs between the cells would give it power.
- The basal × (1 + 1e-3) control in V at 1 and 0.5 ms. It is caught in the amounts at every rung,
  and in V from 0.25 ms down. The protocol picks its δ from its development run, as the coupling
  protocol did.

**Not covered:** A5′ (gated channels), the routing door, and leak and pump targets.

## Independence and disclosure

**Written without the engine.** Nothing here imports `cells` or reads `src/cells/`, the coupling
operator's tests or fixtures (`validation/tissue/regulated_availability_*`), or the FR owner's
branches.

**Read:**
- the coupling design's §0, §4.3–§4.4, §7.2, §9–§10 and Appendix A;
- FR-6 in `docs/FEATURE_REQUESTS.md`;
- the coupling references' usage note and their source (`cells_reference.py` and the
  cross-checks' world builders), which are references, not the operator.

**Not blind:** §9–§10 report the judged A5's engine errors and orders (for example 2.9e-8 V at
1 ms, orders 2.00). They inform nothing here; the margins are against this package's own stand-in.

## Tests

`tests/unit/test_fr6_references_a5pp.py`:
- the registered inputs equal their generator;
- R-cell's run against its floor, and against an independent integration by LSODA;
- the stand-in's second order;
- the s₀ controls caught at every rung (a swapped prior must fail);
- the registered values reproduce.
