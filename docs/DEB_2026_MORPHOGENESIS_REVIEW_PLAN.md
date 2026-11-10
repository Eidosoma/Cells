# Test plan from Deb et al. (2026), a review of multiscale morphogenesis models

D. Deb, O. Parida, L. Naduthota, B. Chakrabortty, "Multiscale Modeling of
Embryonic Morphogenesis from Fertilization to Organogenesis", *npj Systems
Biology and Applications* 12, 156 (2026), doi:10.1038/s41540-026-00788-y, CC
BY-NC-ND 4.0. We read it through Europe PMC (PMC13675182), verbatim up to
reference 62 of 71. This plan cites the paper and reproduces none of its text or
tables. Status: proposed, not yet approved.

## What it is

The article is a narrative review, "representative, rather than exhaustive", of
models from fertilization to early organogenesis. It covers sea urchin, Xenopus,
zebrafish, Drosophila, chick, mouse and C. elegans. It sorts work by framework:

- advection–diffusion–reaction models;
- gene regulatory networks;
- vertex models;
- cellular Potts models;
- agent-based models;
- finite-element and continuum models.

For each framework it names the validation evidence used (its Table 3), for
example laser-ablation recoil and Bayesian tension inference for vertex models.
Its conclusion is that no single level of description suffices, and that a common
multiscale framework with better parameter inference is needed. It has no model,
data or code of its own ("No datasets were generated or analysed").

## Review

**Useful:**

- a map of morphogenesis models by developmental stage and framework;
- named primary studies for systems our ladder can use as benchmarks;
- a list of validation evidence by framework.

**Limits:**

- **No search method.** It is a narrative review with no stated search protocol,
  so coverage is selective by design.
- **No quantitative content.** It gives no parameters, thresholds or comparisons;
  the numbers are in the primary papers.
- **No software.** No reference names open simulation software (tyssue, Chaste,
  CompuCell3D, Morpheus, PhysiCell). This is checked verbatim to reference 62;
  references 63–71 are from a summary.
- **Omissions relevant to us.** No bioelectric morphogenesis (membrane potential,
  ion channels, gap junctions; e.g. BETSE, Pietak & Levin 2017). No
  osmotic or hydraulic morphogenesis (cell volume, lumen pressure). No
  wound-induced electric fields. Integrating these with mechanics is the gap
  Cells is built for, so the review's call for an integrative framework supports
  the track rather than constraining it.
- **Possible mismatches.** Our reader flagged several references whose titles do
  not obviously match the descriptions (CR38, CR55, CR61, CR68). Read the primary
  papers before using any of them.
- **Metadata conflict.** Europe PMC metadata says supporting data exist; the
  article says none.

## What Cells takes from it

The review adds benchmark systems and validation evidence to the existing
[morphogenesis ladder](MORPHOGENESIS_PLAN.md). It does not change the ladder's
order.

| Ladder rung | Addition from the review | Verification in Cells | Primary source to read first |
| --- | --- | --- | --- |
| MG1, passive vertex mechanics | Laser-ablation recoil as validation | Cut one junction in the relaxed tissue; initial recoil velocity against junction tension over friction, compared with the analytic small-strain result and with tyssue run out of process | Farhadifar 2007 (already the MG1 reference; wing-disc ablation data) |
| MG1 | Tension inference as an inverse check | Infer line tensions from a simulated tissue's geometry and compare with the known values (synthetic data only, since inverse methods need validation) | Bayesian tension inference studies cited in the review's Table 3 |
| MG2, T1 and sorting | Convergent extension under anisotropic line tension | Tissue elongation and T1 rate against tension anisotropy, with a reference vertex code | Drosophila germband vertex model (review CR38; check the primary) |
| New, after MG2: purse-string closure | Actomyosin purse-string closure of a gap | Closure rate against cable tension on a fixed-topology ring, then with T1s; links to wound repair and regeneration | Mouse neural-tube closure vertex model (CR48) |
| MG3, growth and division | Agent-based growth checks against lineage-tracing statistics (the review's ABM validation) | Clone-size statistics from growth and division, compared with the wing disc | Wing-disc clone and polygon data (already in the ladder) |
| MG5–6 | Clock-and-wavefront with cell sorting | Somite length against clock period and wavefront speed, on fixed geometry first | CR44 and the Schröter 2008 data already in the ladder |

**Cells' own additions, which the review does not cover:**

- **Bioelectric–mechanical coupling (MG4).** Bistable voltage domains (MG0b) set
  a mechanical parameter. The coupling law, for example a depolarisation- and
  Ca²⁺-dependent contractility, must be sourced from the literature before any
  design (D136).
- **Osmotic and hydraulic morphogenesis.** Once the water model
  (`resolved_pump_water@1`) is qualified, test volume-driven shape change on
  fixed topology before any lumen problem. Literature step first.
- **Wound electric fields during closure.** This joins the purse-string rung to
  the bioelectric layer.

## Order and dependencies

1. **Nothing runs now.** Every addition needs MG1's vertex mechanics, which has
   not started.
2. When MG1 starts:
   - add the recoil test and the synthetic tension-inference check to its
     pre-registered acceptance;
   - read the primary papers for the MG2 and purse-string benchmarks.
3. The bioelectric–mechanical and hydraulic additions follow the qualified water
   model and MG2, through the engine-feature queue (D136).
