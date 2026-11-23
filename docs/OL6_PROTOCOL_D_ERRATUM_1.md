# OL6 Protocol D, erratum 1: D7 under D309's relative clock bound (registration)

**Status: proposed for the lead's tag, 23 November 2026, before D7 runs.** Docs only, with no
change to src, validation or JSON files. Branch `ol6-protocol-d-erratum-1` from main db54d0f5. The
proposed tag is `ol6-protocol-d-erratum-1-2026-11-23`.

**What it amends.** Protocol D as tagged at `ol6-protocol-d-registered-2026-11-23`:
docs/OL6_PROTOCOL_D.md, validation/assembly_lineages_v2/limit_qualification.py and
validation/assembly_lineages_v2/protocol_d.json.
- Those three files are still read byte for byte as tagged, and none is edited.
- This erratum is a fourth registered file. Where it speaks, it is the authority. Everywhere else
  the tagged protocol stands.

**The ruling.** D309 (the user, 23 November 2026, about 10:41 UTC) accepts §7.3's proposal as
written. A step of the deterministic representation is accepted when the pore clock's embedded
error estimate satisfies |U^H| ≤ 1 × 10⁻¹⁰ + 2 × 10⁻³ |ΔH|, with ΔH the step's own clock
increment. This replaces §7.1's absolute 1 × 10⁻¹⁰.

## 1. What changes

1. **The open proposal** (the status paragraph's "One proposal is open") is closed by D309.
2. **§7.1, the bound.** From the engine head of §2 below, every (d) run under this protocol takes
   D309's bound, per vesicle and per accepted step: |U^H_v| ≤ H_ERROR + H_RELATIVE·|ΔH_v|.
   - `rate_equations.H_ERROR` = 1 × 10⁻¹⁰ is its absolute part, unchanged by name and value.
   - `rate_equations.H_RELATIVE` = 2 × 10⁻³ is its relative part.
   - A run beyond the bound is refused. A refused (d) run is inconclusive (numerics) for that
     replica, never a fail, as §7.1 says.
   - §7.1's tolerances stand: rtol 1e-12 and atol_count 1e-9 for D4–D7. So does its stated
     property, the estimate's measured overstatement.
3. **§7.4 and §10: D7 is run.** It is run as registered in §2, §5.4 (E on Δ = T_a − t*_d(E)), §7.4
   (its clock convergence, criterion N) and §9 (its preconditions).
   - None of its worlds, rungs, replicas, seeds, horizon, criteria or tolerances changes.
   - §10's "D7 is 'not run' until §7.3 is settled" no longer applies.
   - Until D7 is judged, the protocol's verdict covers D0–D6. After that, it covers D0–D7, under
     §10's rules.
4. **§7.4's convergence runs at rtol 1e-13 take atol_count 1e-10.** That is 10³ × rtol, the
   ratio of the registered 1e-12 and 1e-9, and the ratio the author's measurement used
   (`clock_tstar_convergence.py`). The tagged text leaves that atol unstated.
5. **The two status lines,** in protocol_d.json and in `limit_qualification.header()` ("D7 held
   for the lead's choice (the protocol's §7), by an amendment tagged before it runs"), are answered
   by this erratum. Neither file is edited.
   - The driver's comment on `INTEGRATORS` (the bound as ruling (a)) changes no number.

## 2. The engine under test for D7

- **D7 runs at the first main head whose history holds D309's bound,** commit 05d50605 (branch
  `ol6-clock-bound`, landed by the lead). The three tagged files and this erratum are unchanged
  there.
- **What the checker records.** As the preamble's "The engine under test" asks, it records that
  revision. It also records every file of `src/cells/models/assembly_lineages_v2/` changed between
  the head at which it read D0–D6 and D7's head.
- **What the bound's landing changes in the family:** one file, `rate_equations.py`. That covers
  the refusal predicate in `_Run.advance_clock`, its words, and two added statistics,
  `largest_clock_error_fraction` and `clock_error_relative`. Any other changed file is listed with
  its landing's D148 proofs.

## 3. Why D0–D6 and the plants stand

- **D0–D6 declare no pore law.** None of their runs holds a pore clock, so none reaches the changed
  predicate: `advance_clock` returns when no clock is carried.
  - Their (d) runs are therefore the same at either head, by construction.
  - Their exact runs are untouched. No exact-path file changed, as the landing's invariance gate
    and probes2 compare show (`/mnt/workspaces/Cells/ol6-20261122/proofs-31f68f4b/`).
- **P-D5 is a pore world,** a held vesicle at a fixed area.
  - Its tolerance reads H_ERROR, which is unchanged.
  - The bound admits or refuses a step and never alters one. The absolute bound admitted P-D5's
    honest and planted runs (§8), so the looser relative bound admits them too, at the same steps.
  - Its outcome therefore cannot change.
- **D7's exact side,** S4's device clock, has no estimate and is untouched.
- **§4's error term** "the pore clock's error is bounded per step (§7)" now reads D309's bound.
  - By the estimate, a crossing time is then within about 2 × 10⁻³ relative while k_v rises (§7.3's
    derivation). That is inside the envelope's mean budget, 2/n_min, for n_min up to 1,000.
  - D7's own convergence check (N) is still what verifies each rung's actual error.

## 4. D7 runs under the bound (measured in (d) alone)

- **The registered ratios** (protocol_d.json, seeds 1–128 at rtol 1e-12): the largest
  (estimate − 1e-10)/ΔH is 4.0 × 10⁻⁶, 3.4 × 10⁻⁵ and 5.3 × 10⁻⁴ at 25, 50 and 100 nm (§7.3). All
  are under 2 × 10⁻³.
- **At the bound's head,** snapshot 31f68f4b with the bound in force, D7 was run in (d) alone:

  | Runs | 25 nm | 50 nm | 100 nm |
  | --- | --- | --- | --- |
  | rtol 1e-12 (registered), seed 1: the largest fraction of the bound used | 0.016 | 0.061 | 0.389 |
  | rtol 1e-13, atol_count 1e-10, seeds 1–6: the largest fraction of the bound used | 0.0025 | 0.0093 | 0.061 |

  - Every run lysed by its pore, and its books closed. No run was refused.
  - At 1e-13 the fraction is the same at every seed. Until its opening, every seed takes D4's
    path.
  - The probe is `/mnt/workspaces/Cells/ol6-20261122/dev/clock-bound/probe_d7_tight.{py,json}`. It
    prints no opening time.

## 5. Not blind (added to §12)

- **Who ran what.** The bound's builder, who is not this protocol's checker, ran D7 in
  cells.rate_equations@1 alone at the bound's head. Those runs are §4's, plus the test row
  `test_d7_s_50_nm_world_runs_under_the_relative_bound` (50 nm, seed 1).
- **What was printed or asserted:**
  - each run's status, causes and steps;
  - the largest estimate, and the fraction of the bound it used;
  - the books' closure;
  - at the opening, H = E to the crossing tolerance.

  No opening time was printed.
- **What was not done:** no exact-event run of any registered world was made, and nothing of an
  exact run was read.
