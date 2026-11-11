# Morphogenesis track: initial plan

Planning of 9 November 2026; nothing implemented yet. Literature values below were
checked against primary sources. The claim-by-claim record (34 claims, 8
corrected, with source URLs), software licences, datasets and recent work are in
`/mnt/workspaces/Cells/morphogenesis-plan-20261109-01/research-verified.json`.
Status lives in [Progress](../PROGRESS.md); experiment definitions in
[Experiments](EXPERIMENTS.md). Rung names (MG0–MG6) are distinct from the
roadmap's M-milestones.

## Why this track

Cells tests how cellular state, tissue organisation and history determine which
forms can be expressed, repaired or reconstructed. Morphogenesis is where those
questions become physical shape. The track starts with patterning and memory on
the fixed tissues Cells already simulates, and adds mechanics once those are
verified. Animal morphogenesis is the long-term target.

## Ladder

| Rung | Question | New engine features | Verification |
| --- | --- | --- | --- |
| MG0a | Does a decaying morphogen from a source reproduce the gradient? | Experiment driver on `reaction_transport@1` (first-order decay, a large-volume source cell) | Exact solution of the discrete linear system; continuum λ = √(D/k) on a regular strip |
| MG0b | Does a bistable voltage domain wall form, show hysteresis and pin at weak coupling, and does it return after cut and restore? | Driver on the channel model `resolved_pump_tissue@3` (Kir2.1, leaks, gap junctions) | Wall width against √G, hysteresis loop, pinning ([McNamara 2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC8008956/); [Keener 1987](https://doi.org/10.1137/0147038)) |
| MG0c | Turing patterning at the predicted wavelength | Reaction terms on fixed tissue | Linear-stability dispersion relation; on zero-flux domains only k = nπ/L ([Maini & Woolley](https://people.maths.ox.ac.uk/maini/PKM%20publications/462.pdf)) |
| MG1 | Does passive vertex mechanics relax to known equilibria? | 2-D apical vertex model: E = Σ K/2 (A − A₀)² + Σ Λl + Σ Γ/2 L² ([Farhadifar 2007](https://doi.org/10.1016/j.cub.2007.11.049)), forces from `jax.grad`, overdamped integration, padded topology | Case-I hexagonal ground state (Λ̄ = 0.12, Γ̄ = 0.04); ordered-network rigidity (shear modulus to zero at p0 = 3.7224) and the T1 barrier bound (vanishing at or above 3.8119, the minimal unit-area pentagon) ([Staddon 2023](https://doi.org/10.1039/D2SM01580C)); junction recoil after ablation and synthetic tension inference ([Deb review plan](DEB_2026_MORPHOGENESIS_REVIEW_PLAN.md)); tyssue run out of process. Bi's disordered p0* = 3.813 needs T1 preparation and moves to MG2 (11 November 2026) |
| MG2 | Does cell sorting follow differential adhesion? | T1 transitions, per-type tension | Tissue surface tensions predicting envelopment order ([Foty 1996](https://doi.org/10.1242/dev.122.5.1611)); the disordered rigidity transition at p0* = 3.813 ± 0.005 ([Bi 2015](https://arxiv.org/html/1409.0593v4)), from T1-relaxed states prepared in the engine; Chaste or Morpheus references |
| MG3 | Do growth, division and death give the observed epithelial topology? Division itself is brought forward as high priority (D141, [cell-division plan](CELL_DIVISION_PLAN.md)), with early embryos first | Growth, division and death, with conserved partitioning of material and charge | Predicted equilibrium polygon distribution: 28.88% pentagons, 46.40% hexagons, 20.85% heptagons, 3.59% octagons ([Gibson 2006](https://doi.org/10.1038/nature05014)). The mean-field model has no 4-sided cells, while the wing disc has 2.95% ([Patel 2009](https://pmc.ncbi.nlm.nih.gov/articles/PMC2688032/)). Lewis's law is fitted, not fixed |
| MG4 | Do bioelectric and chemical prepatterns guide shape and its repair? | Bioelectric–mechanical coupling on moving geometry | Wing disc Dpp gradient: λ = 20.2 ± 5.7 µm (7.7 cells), D = 0.10 µm²/s, k = 2.52 × 10⁻⁴ s⁻¹ ([Kicheva 2007](https://publications.mpi-cbg.de/Kicheva_2007_915.pdf)); scaling λ/L = 0.112 ([Wartlick 2011](https://www.pks.mpg.de/fileadmin/user_upload/MPIPKS/group_pages/BiologicalPhysics/juelicher/Highlights_2011/DoDSaPC2011.pdf)) |
| MG5–6 | Planar polarity, wing-disc growth, then 3-D targets | Polarity; 3-D surfaces | E.g. somitogenesis: clock period 24.9 ± 0.7 min at 27.1 °C, Q10 2.8, temperature-independent somite length ([Schröter 2008](https://publications.mpi-cbg.de/Schr%C3%B6ter_2008_1127.pdf)) |

**History arm.** MG0b is where heredity questions first become testable. A
written voltage domain may or may not return after its tissue is cut and
restored. Planarian anterior–posterior polarity is a parallel fixed-geometry
target, scored against measured outcome fractions ([Durant 2017](https://pmc.ncbi.nlm.nih.gov/articles/PMC5443973/)):
- after octanol, about 25% of fragments regenerate double-headed and about 72%
  are normal-looking but "cryptic";
- 23% of the cryptic animals become double-headed when recut.

**Constraint on MG0a.** A linear steady state is unique, so cut-and-restore on
MG0a tests only the machinery, not memory.

## Engine gaps (in priority order, rough effort)

1. MG0 drivers on existing models (about 1–2 weeks).
2. Vertex mechanics (3–5 weeks). VertAX, a JAX, GPU, differentiable vertex model
   that pads arrays to handle T1 events ([2026](https://arxiv.org/html/2604.06896v1)),
   is the closest prior art. It is CC BY-SA, so it serves as a reference only.
   Potts models are stochastic and non-differentiable, so they serve only as
   external references. Vertex-model parameters can be degenerate
   ([Godolphim 2025](https://arxiv.org/abs/2508.18470)), which limits stress
   inference.
3. Topology events (T1, T2, division, extrusion) with conserved ion, charge
   and material partitioning, remapping edge and junction state (4–8 weeks). This
   is the hardest and most novel part.
4. Growth, division and death, reusing the water/volume and energy families
   (3–4 weeks).
5. Adhesion and polarity (2–3 weeks).
6. Transport on changing geometry: the resolved field must accept time-varying
   areas and lengths (3–5 weeks).
7. Coupling to the bioelectric and regulatory layers (2–3 weeks).
8. Checkpoints and ensembles across topology change, with padded arrays and
   stable world and cell IDs (2–3 weeks).
9. Out-of-process reference runners under `validation/morphogenesis/`.

Electrical (milliseconds) and mechanical (minutes to hours) time scales will
need multirate coupling. The choice of model class can change conclusions
([Osborne 2017](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005387)),
so comparisons should cover more than one reference.

## External references (run out of process, as BETSE is)

| Tool | Use | Licence |
| --- | --- | --- |
| [tyssue](https://github.com/DamCB/tyssue) | First reference: implements the three Farhadifar terms. Our one runner script that imports it carries a GPL-3.0-or-later SPDX header; the rest of the repository stays MIT (user decision, 11 November 2026) | GPL-3.0 |
| [Chaste](https://www.cs.ox.ac.uk/chaste) | Vertex and cell-centre models; Osborne benchmarks for MG2–MG3 | BSD-3 |
| [cellGPU](https://github.com/sussmanLab/cellGPU) | Rigidity-transition statistics | MIT |
| [Morpheus](https://morpheus.gitlab.io) | Potts, ODE and PDE models; sorting and Turing | BSD-3 |
| [CompuCell3D](https://raw.githubusercontent.com/CompuCell3D/CompuCell3D/master/ReleaseNotes.rst) | Potts and PDE models | MIT since v4.3.0 |
| PhysiCell | Cell-centre agents with diffusion | BSD-3 |
| [Tissue Forge](https://tissue-forge-documentation.readthedocs.io/en/latest/introduction.html) | Particle mechanics | LGPL-3.0+ |
| VirtualLeaf2021 | 2-D plant vertex model with reaction–diffusion | GPL-2.0 |
| [Simucell3D](https://doi.org/10.1038/s43588-024-00620-9) | 3-D deformable cells, later | Code licence unverified |

All of these, especially the copyleft ones, run out of process and never link
into Cells. [Leronni 2020](https://doi.org/10.1098/rsif.2020.0177) couples
bioelectricity to mechanics but is built on BETSE, so it is usable in
validation only.

## First organism

The Drosophila wing disc has the best quantitative data:
- measured D, k and λ;
- gradient scaling;
- polygon and ablation data;
- [TissueMiner](https://github.com/mpicbg-scicomp/tissue_miner) pupal-wing
  tracks.

Its bioelectric evidence is relative dye signal only, with no mV values: a
depolarised stripe that regulates Hedgehog ([Emmons-Bell 2021](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8024891/)).
Planarian polarity on fixed geometry runs in parallel for the bioelectric link.
The ascidian ASTEC datasets (CC BY 4.0) add an embryo-halving repair case.

## First experiments, pre-registration elements

- **MG0a:**
  - discrete profile within 1e-9 relative of the exact linear-system solution;
  - continuum λ within 1% on a regular strip (the discretisation error is about
    0.07% at 7.7 cells);
  - mass residual below 1e-9 relative;
  - expected convergence order.
- **MG0b:**
  - wall width scaling with √(gap-junction coupling);
  - hysteresis loop and its width reported, not tuned;
  - wall pinning below the predicted coupling;
  - cut-and-restore outcome pre-declared as either "returns" or "does not
    return", with controls (no cut; cut without restore; uniform state).

## Risks

- Mechanics is a large new model family, and MG0 does not test shape.
- Topology events break fixed-shape compilation and checkpoints.
- Conserved partitioning across division and T1 is novel.
- Bioelectric morphogenesis data are mostly qualitative or relative.
- Scope can creep towards animal targets too early.
