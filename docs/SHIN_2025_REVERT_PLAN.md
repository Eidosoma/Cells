# Backlog plan: Shin et al. (2025), attractor landscape and a reversion switch in colorectal tumorigenesis

D. Shin, J. R. Gong, S. D. Jeong, Y. Cho, H.-P. Kim, T.-Y. Kim, K.-H. Cho,
"Attractor Landscape Analysis Reveals a Reversion Switch in the Transition of
Colorectal Tumorigenesis", *Advanced Science* 12(8), e2412503 (2025),
doi:10.1002/advs.202412503, CC BY 4.0. Read through Europe PMC (PMC11848608),
almost entirely verbatim. The supplement (Tables S1–S3, Figs S1–S9) and the GEO
record GSE283167 were not read. Code: <https://github.com/dshin-ncc/REVERT>, read
at commit `8ee0651` (2024-12-02). The repository has no licence file.

Status: backlog. Nothing runs before the user approves a reproduction (see the
end of this plan).

## What the paper does

**The REVERT framework**, built on single-cell RNA-seq of matched tumour and
adjacent-normal colon organoids from one patient (18,049 cells), runs in five
steps:

1. Infer copy-number variation (CopyKAT) and build a clone tree.
2. Locate a "transition state" from per-clade entropy.
3. Order cells along a pseudotime trajectory (Monocle2).
4. Build a core Boolean gene-regulatory network:
   - a SCENIC prior;
   - Spearman pruning;
   - rules fitted to binarised pseudotime pairs with a Z3-based search;
   - 10–30 nodes;
   - synchronous updates in BoolNet.
5. Analyse its attractors:
   - nine attractors from 1,000 random starts in Fig. 3d;
   - one cancer-like attractor and one normal-like attractor, assigned from the
     pseudotime ends;
   - a "cancer score" combining attractor entropy under perturbation, basin size
     and a normalised projection distance between the normal and cancer states.

**In silico perturbation and target selection:**

- The network's best single perturbation is YY1 knockdown, and its best pair is
  YY1 plus MYC (cancer score 0.056).
- The authors set YY1 and MYC aside for drug tractability.
- They then chose USP7 among shared SCENIC targets of MYC and YY1, using DepMap
  dependency scores and LINCS normal-colon signature enrichment (Sect. 2.5).
- The USP7 inhibitor P22077 (5–20 µM, 10 days) reduced the growth of the same
  patient's tumour organoids and shifted expression toward normal-colon
  signatures.

## Review

**Safe to state now:**

- **One patient.** The transition analysis and the validation rest on one
  patient's organoid pair.
- **Updating scheme.** Updates are synchronous, which can create attractors,
  especially cyclic ones, that asynchronous or continuous-time versions do not
  have. The paper does not test robustness to the scheme.
- **USP7 was not predicted by the network.** In the paper's own words (Sect. 2.5),
  the network pointed to YY1 and MYC. USP7 was selected by combining cancer
  dependency and normal-signature enrichment scores. Sect. 2.6 nevertheless
  describes the result as supporting the Boolean model's predictions.
- **The perturbation was a drug.** It was the small-molecule inhibitor P22077,
  with no genetic knockdown, although the text and captions say "knockdown".
- **Missing controls:**
  - no normal-organoid control;
  - no in vivo work;
  - smaller organoids do not by themselves show reversion rather than growth
    inhibition or stress.
- **The repository does not reproduce the paper:**
  - its data are a 1,000-cell, 5,000-gene subset;
  - it holds no committed node list or rule set;
  - it has no code for the cancer score or the perturbation scan;
  - it has no licence file;
  - its committed settings differ from the paper's, for example a correlation
    cutoff of 0.8 against the stated 0.7, and 100,000 attractor starts against
    1,000 or 10,000.
- **Circularity.** The rules, the attractor labels and the trajectory all come
  from the same cells. The authors note that the dominant cancer basin partly
  follows from choosing a normal-to-cancer trajectory.

**To check against the figures and supplement before stating:**

- nine attractors (Fig. 3d) against five (Fig. 4c);
- a success threshold of 0.1 (Methods) against 0.15 (Results);
- the 20 µM arm in Methods but not in Fig. 5f;
- alignment to the mouse genome mm10 for human bulk RNA-seq;
- one patient against the mention of "external validation biopsies";
- the number of hyperparameter sets behind "the majority of cases";
- replicate counts and effect sizes for the organoid growth result.

**Useful:**

- the attractor-landscape view of a fate transition;
- basin size from sampled starts, and convergence entropy under perturbation, as
  quantitative landscape measures;
- the question of whether a reversion switch exists, which parallels rewriting a
  stored bioelectric state.

## Quick check of the published rules (11 November 2026)

The user supplied Supplementary Tables S1–S3. We enumerated every one of the
2¹⁷ = 131,072 states of the 17-gene combined network in Table S2. This is a
development check of the paper's network, not a Cells engine model; evidence is
in `/mnt/workspaces/Cells/paper-shin-2025-revert-20261111-01/`.

- **31 attractors, all fixed points.**
  - The asynchronous terminal sets are the same 31 single states, so this
    network's attractors do not depend on the update scheme. That answers the
    synchronous-updating concern for this network.
  - The paper reports nine attractors, one of them cyclic, from 1,000 random
    starts. That may describe a different network size (Table S3 lists 13-, 17-
    and 21-node networks), and 1,000 starts miss most basins here, many of which
    are under 1% of states.
- **The many attractors come largely from self-loops.**
  - Six genes keep themselves on: BHLHE40, CDX2, DDIT3, KLF6, RELB and YY1.
  - FOXO3 also needs JUN.
  - The inference adds self-activation to any node without an activating input,
    so the landscape's multiplicity is partly an artefact of the method.
- **Cancer-like states.**
  - 12 fixed points have MYC, CDX2, YY1, SREBF1 and SMARCA4 all on; together
    their basins hold 87.5% of states.
  - Table S3 reports a basin size of 875 for several networks, possibly 875 of
    1,000 starts. That matches 87.5%, but this is not confirmed.
- **Clamping both YY1 and MYC off removes every state with MYC or YY1 on.**
  - 14 fixed points remain.
  - Fully normal-like states, with all five cancer genes off, take about 22% of
    states.
  - The largest remaining basins keep CDX2 on, through its self-loop.
- **One knockdown alone does not do it.** Clamping YY1 off leaves MYC-on states
  in the largest basins. Clamping MYC off leaves YY1-on states. This agrees with
  the paper's statement that the combination is needed.
- **Table S3:**
  - YY1 plus MYC is the best double perturbation in most of the 19 listed
    hyperparameter cases, with final scores of 0.038–0.143.
  - SREBF1 plus MYC and YY1 plus CDX2 also appear.
  - The network size varies from 13 to 21 nodes with the settings.
  - The BasinSize column mixes fractions (0.36–0.73) with the value 875, so its
    units are unclear.

So the published rules reproduce the in-model claim that a YY1 plus MYC knockdown
removes the cancer attractors. The robustness and causal questions in the review
above are unchanged by this check.

## What "model it in Cells" can mean

The model is a data-inferred Boolean network with no rate constants, ions,
voltage or tissue physics, so no Cells engine model can run it as published.

| Group | What | In Cells |
| --- | --- | --- |
| 1. Outside reference (tooling) | Reproduce the attractors with the authors' code, run as-is outside Cells. Then test whether they survive asynchronous updating and a continuous-time version of the same network | Needs the rules from Tables S1–S2, or a rerun of the inference on the GEO data. Needs the user's approval; the code has no licence, so run it only and never copy it |
| 2. Needs an engine feature | A gene-regulation layer with sourced kinetics, coupled to cells | The same feature as heredity Stage D and parity rung P8. Cells has an isolated, source-backed regulatory model (`emt_mirna@1`, the miR-200/ZEB EMT circuit) and closed compartment chemistry (`compartment_reactions@1`), but no regulation coupled to tissue |
| 3. Needs growth | Organoid size, the paper's only wet readout | MG3 (growth and division) |
| 4. Not transferable | The patient-specific rule set as an engine model | D136: no biological kinetics or parameter sources |

**What transfers now.** The landscape measures apply directly to Cells'
bioelectric attractors: the H and D patterns of `resolved_pump_tissue@3`. They
are:

- basin size from sampled initial states;
- convergence entropy under perturbation.

They belong to tests T3 and T4 of the [Cortés-Poza plan](CORTES_POZA_2026_TEST_PLAN.md).
The paper's projection distance is not adopted as a recovery score, because it
ignores change off the normal–cancer axis, the same weakness as a one-sided
fidelity metric.

**A Cells-specific question, a hypothesis only.** Does membrane voltage shift a
fate network's attractor landscape? The paper has no voltage content. Any
voltage-to-fate coupling (for example through Ca²⁺ or Wnt/β-catenin) needs its
literature step first, under D136.

## Order (backlog)

1. **After** Cortés-Poza Phase 0 and cell replacement (G2).
2. **First:** obtain the supplementary rules and the GEO sample list, then ask the
   user to approve the group 1 reproduction.
3. **The landscape measures** go into Cortés-Poza Phase 1, on the engine's
   bioelectric attractors.
4. **Groups 2 and 3** wait for the gene-regulation layer and MG3.

Patient-derived data stay under `/mnt/workspaces/Cells`, never in this
repository.
