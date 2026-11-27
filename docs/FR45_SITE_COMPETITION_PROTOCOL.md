# FR-45's qualification: competing ligands on one shared, wash-retained site set (registration)

**Status: drafted for the lead's tag, 23 November 2026,** before FR-45's build and before any engine
run (D327). Docs and validation only, with no `src/` change. Branch `fr45-protocol` from main
872dc2d2. The protocol is `fr45-site-competition-v1`. The proposed tag, at the final head after the
references agent's work, is `fr45-protocol-registered-2026-11-2x`.

**What it registers:**
- this document;
- the reference spec, `validation/fr45/spec/SPEC.md`;
- the criteria, bands and plants, `validation/fr45/spec/CRITERIA.md`;
- the pair rule, `validation/assembly_lineages_v2/agreement.py`, FR-47's (D323), which is not yet on
  main (§8);
- the dated changes of 24 November 2026, before the tag, in `validation/fr45/spec/`:
  - `AMENDMENT-2026-11-24.md`, the references agent's 13 questions;
  - `NOTE-2026-11-24.md`, C4b's and C6's state;
  - `AMENDMENT-2-2026-11-24.md`, the user's acceptance targets: W7, the user's example washed, and
    W7s, its single-ligand limit;
  - `AMENDMENT-3-2026-11-24.md`, the references agent's findings on them: W7 and W7s step at
    0.0025 s, W7s runs to 2.0 s, and P5's entries are keyed by state;
- at the tag, the code-blind references' code and files, in `validation/fr45/references/`.

**Engine models it runs:** `resolved_pump_composite@1` over `resolved_pump_tissue@3`, with
`site_occupancy@1` widened by FR-45's site sets, and `scheduled_compartment_wash@1` in W2 and W7.

**S** marks this document's own reading or derivation.

## 1. The claim

**The build** (D327) widens `site_occupancy@1` in place with shared site sets. Several one-ligand
populations compete for one set's free sites, under the competitive Langmuir law. Version 1 binds
only:
- internalisation, and `site_occupant_replacement@1`, are refused beside site sets;
- `species_regulated_availability@2` reads a shared set's θ_b.

**The qualification shows, against code-blind references:**
- **R-eq, the finite-volume equilibrium.** Competing ligands deplete their pools and share each
  set's capacity. The engine's state at the horizon is the root, and the engine started at the root
  stays there.
- **R-ode, each ligand's balance.** The trajectories and the books follow each ligand through bind,
  wash and unbind:
  - the wash removes only the liquid's ligand;
  - the shared capacity is conserved across it;
  - the bound sites are left bit for bit, shown on the wash operator alone.
- **R-dG, the shared-site heat.** It is booked with a set's free sites counted once, and it never
  falls.
- **Beside these:**
  - the stage condition's free-site load, summed over a set's populations;
  - the engine's third order at fixed concentrations;
  - θ_b, the quantity @2 reads.

**Version 1's refusals, by name** (the build's; a row each in its tests):
- internalisation on a shared set, or in a component that internalises;
- `site_occupant_replacement@1` in a world that declares site sets;
- a set named by fewer than two populations;
- two populations of one set binding one ligand;
- initial occupancies over 1 on a set.

## 2. Why the references are exact (S)

### 2.1 R-eq

- **The equilibrium is the root of explicit equations.** Each population satisfies detailed
  balance, B_b/R_s = c/K_b, and each ligand's total and each set's moiety are fixed.
- **For one set and ligands that bind it once,** R solves R + Σ N_l·R/(K_l·V + R) = S. Its left
  side is strictly increasing in R, so there is exactly one root in (0, S).
- **For two ligands** it is a cubic, which has a trigonometric closed form (Wang 1995).
- **Coupled sets** (W3) give a small system, solved by the references.
- **The engine's scheme has this root as its fixed point.** At equilibrium every route's extent is
  zero. Probed before this spec: one half-step started at the root moves no pool, and a relaxation
  meets the root to 6·10⁻¹⁵ relative (the design note's §14.1).
- So C2's tolerances are derived from the representation alone.

### 2.2 R-ode

- **The trajectories have no closed form under depletion.** The references integrate the declared
  equations at two tight tolerances, and report the gap between them.
- **At fixed concentrations (W4) they are linear,** with a closed form, e^(A·t). The references
  check their integrator against it, beside the node's 2·10⁻⁹ depletion.
- **Each ligand's total** and each set's moiety are exact constants of the equations. The wash's
  map is explicit (SPEC.md §1.4).

### 2.3 R-dG

- **G is a state function:** the lattice free energy of each set, with R once, plus the pools'
  ideal terms.
- **A closed, passive sub-system's heat** over an interval is G(start) − G(end), exactly. The
  references compute it from their states, and the judge recomputes it from the engine's (C3b).
- **The heat's error against the reference** is C1's band carried through G's derivatives (C3a).

## 3. The rule at zero uncertainty (D323, D327)

- **Every zero-uncertainty pair is classified in the reference's file before any run,** by FR-47's
  rule (`agreement.py`):
  - `constant`: bit for bit (C6, C7, C10);
  - `derived`: two routes to one constant by different arithmetic, within a tolerance computed
    from that arithmetic (C2b, C3b, C3c, C4a, C4b, C5, C9).
- **No pair is `spread`:** nothing is drawn.
- **The trajectory pairs carry the engine's integration error.** They are judged by bands: C1's,
  C3a's and C4c's derived from it, and C2a's at the horizon. C8 shows the error's order.
- No class or pair changes after a run.

## 4. The worlds (SPEC.md §2 holds every input)

| World | What | Criteria |
| --- | --- | --- |
| W1 | One node-owned set, two ligands, from empty sites, in a 1 pL node | C1, C2a, C3, C5, C9, C10 |
| W1eq | W1 started at its root | C2b |
| W1p | W1 cut to 6.4 s | the plants P1–P3, P6, P8, P9 |
| W2 | Bind, wash and unbind in a 1 µL node: L1 bound at its own equilibrium, then half the liquid washed for a buffer holding the competitor L2, which displaces L1 | C1, C2a, C3, C4, C5, C6, C10 |
| W3 | A three-ligand set and a one-population set sharing L2 at a node, and a two-ligand set on a patch's inside face in the cell | C1, C2a, C3, C5, C9, C10; W3p (cut to 2 s) for P7 |
| W4 | Fixed concentrations in a 1 mL node, at three steps | C8 |
| W5 | The stage condition's edge: each population at h·k_on·c = 0.3, summed 0.6 | C7, P4 |
| W6 | A two-ligand set on a patch's outside face, from partial occupancies | C1, C2a, C3, C5, C9, C10 |
| W7 | The user's example (amendment 2): 8 fmol free A and 4 free B over 6 fmol of shared sites (3 empty, 2 A, 1 B), at its own equilibrium, then half washed for a buffer holding B | C1, C2a, C2b (before the wash), C3, C4, C5, C6, C9, C10, P5 |
| W7s | W7's single-ligand limit (amendment 2): A alone on W7's sites | C1, C2a, C3, C5, C9, C10 |

**Every world's step meets dt·max L ≤ 0.03,** sized before this spec by a NumPy probe of the same
law. Two worlds are exceptions by design: W4's coarser runs (the order study) and W5 (the
refusal). **Every horizon of W1, W2, W3, W6, W7 and W7s reaches e⁻³⁰ of its slowest mode,** and
none goes so far beyond it that an interval's heat falls below the references' resolution
(amendment 3: W7s's 2.0 s is 47 time constants). W1eq starts at
its root, and W1p, W3p, W4 and W5 are short by design.

## 5. The judged run

- **When:** once FR-45's build has landed and `agreement.py` is on main, from a clean snapshot of
  main, with the references tagged.
- **The judge** (`validation/fr45/judge.py`, the build's, under `validation/`) first reads the file
  the writer wrote on invented inputs, then the engine's runs.
- **The protocol passes** when every criterion passes and every plant is caught.
- **It fails** if any criterion fails or any plant escapes.
- **Inconclusive** arises only from the references' own convergence (CRITERIA.md). That is resolved
  before the tag.

## 6. What it does not show

- internalisation under competition, and the occupant-replacement operator beside site sets
  (refused in version 1);
- labels beside sites (refused, D327's later items);
- a run of the coupling operator: only the quantity it reads (C9);
- faces at a set's node, division, stochastic binding, regulated accessibility;
- any comparison with data. This is numerical qualification (D138).

## 7. Disclosures (dated 23 November 2026, before any run)

- **This document's author probed the worlds' shapes** before writing the spec, with a NumPy and
  SciPy integration of the same law: the scheme written from the site note, generalised to a shared
  R. The probes are in /mnt/workspaces/Cells/fr44-45-design-20261123/probes/:
  - `competition_probe.py`: W1's fixed point, the fixed-concentration order and the heat sign;
  - `fr45_world_sizing.py`: each world's equilibrium, slowest rate and largest load.
- **The first sizing printed the equilibria of W1's and W2's earlier inputs,** and a probe printed
  the scheme's errors at W4's earlier inputs.
  - All three worlds' inputs were re-chosen the same day, sized on loads and slowest rates alone.
    The registered inputs' equilibria and trajectories have not been seen.
  - W3's and W6's printed sizing gave rates and loads only. W3's one equilibrium printed was at an
    earlier L3 rate, since changed.
- **The criteria were dry-run before registration** on neighbouring inputs, never the registered
  ones (`fr45_criteria_dry_run.py`). An honest emulation of the scheme was pushed through every
  formula, and only each criterion's statistic was printed. CRITERIA.md lists the margins.
  - C2a's first, derived form failed that honest emulation, so it is a band.
  - C8 was restricted to R and B.
  - C1 moved to the node's scale.
  - C3a's log term takes max(x, δ).
  - W3's and W6's observation times were put on their grids.
- **main (872dc2d2) admits dt = 0.1 and 0.05 s in a site world** (`coarse_step_check.py`, the wash
  fixtures' well). So W5's refusal can come only from the stage condition.
- **No engine run of any registered world exists.**
- **The bands come from the scheme's order and the dry run, not from any engine result.** C1's
  10⁻⁶ was met at 0.17 of itself, and C8's ratio rule restates third order: 8 per halving, against
  8.35 and 8.17 in the dry run.
- **The design note** is /mnt/workspaces/Cells/fr44-45-design-20261123/DESIGN.md (§9 to §17),
  approved in D327.

## 8. Order and dependencies

1. **The code-blind references agent,** at the lead's go:
   - it reads only `validation/fr45/spec/` and this document;
   - it writes `validation/fr45/references/` on its own branch, with the writer and its test on
     invented inputs;
   - it shows the regeneration under two other hash seeds.
2. **The tag**, before any engine run.
3. **FR-45's build** in `site_occupancy.py`, which its builder owns before FR-49. Before any
   crossrev baseline is renewed (D327):
   - D148's compatibility on FR-3's existing worlds, their derivative programs included, with a
     check of whether FR-3's judges take derivative programs;
   - the full new crossrev record, written first from a clean snapshot of main, in a new record
     folder. record-cda5dc82 is left untouched, and its read-only replication/ never modified.
4. **`agreement.py` on main,** with FR-47's protocol, or landed alone before the judged run since
   it is shared.
5. **The judged run** (§5).

## References

- Wang Z-X. An exact mathematical expression for describing competitive binding of two different
  ligands to a protein molecule. *FEBS Lett* 1995;360(2):111–114. doi:10.1016/0014-5793(95)00062-E.
  The record was checked by Crossref, 23 November 2026; the text was not read. The cubic in the
  free-site variable is derived in the design note (§11).
- Motulsky HJ, Mahan LC. The kinetics of competitive radioligand binding predicted by the law of
  mass action. *Mol Pharmacol* 1984;25(1):1–9. PMID 6708928. The record was checked in the site
  note. W4's linear kinetics are its case.
- The site note (`docs/SITE_OCCUPANCY_DESIGN.md`), the wash note (`docs/COMPARTMENT_WASH_DESIGN.md`),
  FR-47's protocol (`docs/FR47_SHELL_EXCHANGE_PROTOCOL.md`, for the rule at zero uncertainty), and
  D148, D323 and D327.
