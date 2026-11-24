# Cells proofs

Browse Cells engine laws by scientific topic. Each claim links its Lean proofs, tested engine code and biological measurements. [Current law and operator coverage](COVERAGE.md) · [Failing numerical checks](COVERAGE.md#failing-numerical-checks) · [Latest comparisons and engine findings](PROGRESS.md)

## Proof index

<!-- generated: claims-index -->

Direct Lean claims cover [55 of 55 laws](COVERAGE.md#registered-laws) and [35 of 35 operators](COVERAGE.md#registered-operators).

| Category | Registered laws with proof | Claims with proof | Numerical checks | Claims with biological evidence |
| --- | ---: | ---: | --- | ---: |
| [Membrane transport and osmosis](COVERAGE.md#category-membrane-transport) | 6 of 6 | 11 of 11 | 11 checked | 10 |
| [Ion channels and junctions](COVERAGE.md#category-channels-and-junctions) | 15 of 15 | 15 of 15 | 15 checked | 14 |
| [Pumps and cotransport](COVERAGE.md#category-pumps-and-cotransport) | 13 of 13 | 9 of 9 | 8 checked · 1 open | 9 |
| [Reactions and binding](COVERAGE.md#category-reactions-and-binding) | 3 of 3 | 18 of 18 | 16 checked · 1 failed · 1 open | 13 |
| [Molecular assembly and catalysis](COVERAGE.md#category-molecular-assembly) | 16 of 16 | 46 of 46 | 44 checked · 1 failed · 1 open | 28 |
| [Tissue transport and conservation](COVERAGE.md#category-tissue-and-conservation) | 2 of 2 | 29 of 29 | 28 checked · 1 failed | 21 |
| [Cell physiology](COVERAGE.md#category-cell-physiology) | — | 3 of 3 | 3 checked | 3 |

<!-- /generated -->

Each category opens its detailed claim table on GitHub. A covered law or operator has at least one directly proved property, with its assumptions listed on the claim page. The last column counts claims with a recorded measurement or literature finding, including partial evidence. Each numerical result applies to the cases in its linked record. [All registered laws](COVERAGE.md#registered-laws) · [Design notes](ENGINE_LAW_VERIFICATION.md) · [Voltage pilot closeout](../reports/BIO003_PILOT_CLOSEOUT.md)

The original reversible GARD v1 law can refuse an extreme catalyst ratio, and the rapid-binding solver can misclassify a ligand inventory at the limit of binary64 precision. The XC0 initial charge check also refuses balanced inputs at large ion inventories. The Lean bound distinguishes those from deliberately mischarged inputs. The repaired FR-38 retention check detects an unresolved export interval. Its separate survival check now accepts the one-step rounding discrepancy and still rejects a changed loss rate. The public pore-clock cutoff and all four lossless RNA fate records also pass their earlier controls. [Current failures](COVERAGE.md#failing-numerical-checks) · [XC0 rounding controls](claims/xc0-charge-anchor.md) · [Retention repair](PROGRESS.md#fr38-retention-window-repair) · [Survival repair](PROGRESS.md#fr38-survival-rounding) · [Pore-clock retest](PROGRESS.md#fr31-pore-endpoint-repair) · [Lossless RNA retest](claims/release-fate-export.md)

FR-42’s neutral arrival-time labels now have a proof and a compiled comparison. With constant loss and arrivals, every positive final amount up to the available supply determines a unique loss exponent. The label amounts sum to the physical pool. Enabling labels preserved all 42 shared history fields and 76 shared observations bit for bit in the tested tissue. With quadratic loss, the new cohort held 0.24999987 fmol at one second, against the exact ¼ fmol. [Finite-step proof and checks](claims/fr42-survival-exponent.md) · [Quadratic cohort and blank](claims/fr42-cohort-shares.md)

FR-38 follows a producer’s RNA from template release through cell replacement. Lean bounds the old producer’s RNA inside a replacement cell by cumulative return. The public development fixture passed all 14 checks. The independent registered comparison **failed R1** and found **R2 inconclusive**. The follow-up traced route 1 to a gross-versus-net loss comparison. [Producer balance and restart](PROGRESS.md#fr38-extracellular-producer) · [Registered verdict D313](https://github.com/Eidosoma/Cells/blob/81a98ca025ee662a0846aa13868dfc93fa87ea22/docs/DECISIONS.md#L9867) · [Route-1 diagnosis D316](https://github.com/Eidosoma/Cells/blob/a8f9810c791986a25a38f8ecb718cbfdf7479fec/docs/DECISIONS.md#L9972)

## Biological evidence

In a measured nucleotide pool, upstream depletion and downstream product predicted 0.822 mM UTP at seven hours, compared with 0.955 ± 0.350 mM measured (SD). The FR-43 development replay checks how much each of two writers contributed and which volume each used. [Shared-pool proof, native runs and measurements](claims/fr43-shared-writers.md)

Deterministic assembly reactions reverse direction across equilibrium and dissipate free energy. Two measured enzyme time courses show opposite net conversion from opposite starting sugars. In a separate rabbit-muscle preparation the kinetic inputs gave a Cells stall ratio of 0.32, compared with a measured F6P/G6P ratio of 0.30. [Reaction proof, compiled checks and measurement limits](claims/rate-equation-flux.md)

The reaction integrator preserves closed material inventories through its stages and dense output in exact arithmetic. A partially purified enzyme assay recovered 100.2% of the initial G6P + F6P at 30 minutes. In one cell-extract course the measured pair fell by 22.29%, limiting which experiments can test the closed-pool assumption. [Conservation proof, native replay and both assays](claims/rosenbrock-inventory.md)

Mobile carriers can move a ligand even at zero net binder flux. Rabbit heart cells show faster acid arrival with carbonic buffer, and myoglobin increased initial oxygen flux across a polymer film. The Cells comparison follows free and bound ligand separately to both ends of a face. [Measurements, proof and compiled tissue comparison](claims/forms-face-carriage.md)

How long does released RNA survive? A purified bacterial assay measured the fraction detached, a human ACTB time course gave a 3.35 min chromatin-association half-time, and yeast ASH1 counts declined with a reported half-life of 6.1 ± 2.8 min in 21 cells. Each measurement answers a different part of the question. The Cells chase fraction still needs a cohort marked at detachment and counted again after its marking window closes. [Three measurements, denominators and sources](claims/release-window-survival.md#biological-evidence)

After delivery, placental lactogen RNA remained detectable in maternal plasma in 4 of 13 women at two hours. In a separate mouse-cell study, recipients unable to make the assayed RNA carried about 370 donor copies per cell at 24 hours. These results test persistence of a source-specific signal and donor attribution. Gross return rates remain open. [RNA measurements and limits](claims/producer-replacement-rna.md#biological-evidence)

Thirteen mitochondrial recordings provide three measured proton-current reversal voltages. Cells reverses in the measured direction at all three gradients. Each predicted voltage falls within its group’s descriptive 95% interval for the mean. Absolute leak current requires a separate calibration. [Measured voltages, uncertainty and proof](PROGRESS.md#mt1b-buffered-reversal)

In two mock-treated mouse dendritic-cell replicates, heavy-labelled Actn1 accounted for 17.19% and 10.11% of the paired isotope signal at five hours. The two measurements show how to observe a cohort fraction. Amino-acid recycling limits how closely that fraction follows newly made protein. A common loss rate across cohorts remains open. [Measurements and source accessions](claims/fr42-cohort-shares.md#biological-evidence)

Five held-out DOPC rupture rates passed the registered two-sided temperature test. Cells also predicts how the opening and release share the heat. An independent temperature series measured local rotational viscosity, and a nanoscale fluctuation experiment estimated surface viscosity at one temperature. The heat split and the temperature dependence of friction at a critical pore remain open. [Rupture rates and experimental limits](claims/vesicle-pore-rate.md#biological-evidence) · [Heat and viscosity evidence](claims/vesicle-pore-heat.md#biological-evidence)

During mechanical division of a liposome, one daughter can rupture while its sibling survives. Cells now reconciles the returned material in both runners. The experiment measured sibling fluorescence and external dye spreading in separate analyses. A same-event measurement of where the ruptured daughter’s contents went remains open. [Rupture at birth](claims/vesicle-birth-returns.md) · [Sibling fates, Fig. 1d](https://ceesdekkerlab.nl/wp-content/uploads/2019/08/Mechanical-division-of-cell-sized-liposomes.pdf#page=2)

The osmotic volume law has **mixed biological evidence**. Fujiwara and Yanagisawa’s liposomes shrank to about 25% of their starting volume, against 24.56% in Cells without fitting. Wolfisberg’s four later volumes were below prediction. In Bhatia’s vesicle, the uncertainty in the outer contour spans the difference after accounting for the inward tube. [Three preparations side by side](PROGRESS.md#intact-vesicle-deflation) · [Generated claim and primary sources](claims/osmotic-vesicle-volume.md#biological-evidence)

At the same growth rate, measured fractions of mRNA-bound ribosomes in *E. coli* ranged from 31% to 65% across three nutrient limitations. In hamster cells, tracer measurements followed residues in unfinished and released protein separately. These experiments give observables for the two polymerisation balances. A quantitative Cells comparison still needs matched conditions and pool definitions. [Machine occupancy](claims/polymerisation-machines.md) · [Residues in transit and released](claims/polymerisation-residues.md)

In a purified *E. coli* experiment, polymerase remained on DNA after RNA release in 87 of 100 selected traces. Separate recordings also detected new RNA synthesis by retained polymerase. Both Cells options for returning polymerase conserve its pool. The experiment leaves open when that polymerase becomes available to other templates. [Measurement and both engine comparisons](PROGRESS.md#fr38-terminal-inventories) · [Harden et al., Figures 1 and 3](https://pmc.ncbi.nlm.nih.gov/articles/PMC6978322/)

In a matched Cells control, a donor loses the same amount of labelled protein under transfer and degradation. A receiver gain or a clearance record distinguishes the mechanisms. Imaging of PSD-95 shows label spreading from one spine to two neighbors. The fate of the original label across the whole neuron over 48 hours remains open. Representing a neutral tracer by separate species rows can also change the heat attributed to mixing. [Matched donors](claims/transfer-or-degradation.md) · [Whole-cell balance](claims/regional-pulse-balance.md) · [Neutral label diffusion](claims/neutral-label-diffusion.md) · [Effect on booked heat](claims/label-mixing-power.md)

At 0 mV, the published Kv1.5 activation curves predict 72.1% retained current at pH 6.8 if both preparations share a maximum conductance. A separate pulse in the same study gave 74.5 ± 1.9% (SEM). Applying only the measured midpoint shift to the default Cells gate gives 40.5%. [Kv1.5 pH comparison](claims/kv15-ph-activation.md)

For Kv1.5 in HEK293 cells, a density-inhibition curve fitted to the two endpoints predicts a conducting fraction of 0.22 at 300 channels/µm². The same figure gives about 0.23 there, without a pointwise uncertainty. An independent channel count lets a fixed-gate current comparison distinguish changes in availability. [Density comparison](claims/channel-density-availability.md) · [Clamp proof](claims/clamped-channel-current.md)

The biological review identifies three engine opportunities with measured targets. It covers the reversal of the yeast vacuolar proton pump, the time to rupture of a vesicle under steady tension, and fast and slow closure of Cx43 gap junctions. [Measurements, current engine results and proposed changes](PROGRESS.md#biological-model-review)

The Cx43 polarity measurements bound the error of the registered single-gate law. The registered two-gate law satisfies the predicted amplitude relation on synthetic clamps and runs in the tissue host under its development flag. Resolving the mixed amplitude in a measured Cx43 trace remains open. [Measurements](PROGRESS.md#cx43-series-gates) · [Compiled comparison and host replay](PROGRESS.md#nov21-registered-series-and-withdrawal)

A serial dilution experiment follows free fluorescein through three successive exchanges, including the discrepancy at the third 80% wash. For uneven sampling, a separate experiment measured approximately 75% and 25% of stock dye concentration in two outlets carrying equal flow. Measuring the dye left in each region after a finite draw would test the Cells remainder prediction. [Measured dilution](PROGRESS.md#nov21-wash) · [Two-region draws and dye measurements](claims/two-region-sampling.md)

For partial pool withdrawal, one passive splitter collected a mean of 45.0% of each droplet’s beads in a nominal one-third branch. Another retained 28.2% of beads at a mean liquid fraction of about 27.2%. A test of count variance still needs particle counts and liquid volume measured on the same split. [Count proof and measurements](claims/pool-withdrawal.md) · [Paired-data search and heat proof](PROGRESS.md#fr35-withdrawal-energy) · [Biological disagreements for Cells](PROGRESS.md#nov21-biological-disagreements)

For finite-pool washes, tracer measurements distinguish what leaves the exterior, what survives inside a vesicle, and what can later enter another membrane. The deterministic shell also reproduces the predicted free-energy drop during refill. A direct experimental measurement of that drop remains open. [Washout and redistribution measurements](claims/pool-replacement.md#biological-evidence) · [Post-wash tracer counts](claims/fr47-shell-wash-recovery.md) · [Interval heat and experimental scope](PROGRESS.md#fr47-shell-interval-heat)

For a wash of a solid surface, the first saved step can already include tracer released from the wall. An albumin experiment measured both rinse liquid and the final surface residue. The time course of release in that preparation remains open. [Wall retention and measured albumin recovery](claims/wall-wash-retention.md)

Yeast mitochondrial ATP synthase provides a measured example of reversal. The enzyme switched from hydrolysis to synthesis as the proton gradient increased. Cells captures the shift between the lowest and highest ATP loads. The comparison also records the four intermediate measurements outside the combined interpolation limits. [Mitochondrial stall and biological evidence](claims/mitochondrial-stall-heat.md#biological-evidence)

In isolated rat liver mitochondria the intermembrane space was up to 0.5 pH units more acidic than the bath. The three-compartment control shows that substituting bath pH can reverse the predicted leak. The uncoupled mitochondrial gradient remains a separate measurement target. [Proton compartment and experimental scope](PROGRESS.md#mt1b-local-proton-read)

The catalog gives each measurement, its primary source and the part of the law it tests. **Partial evidence** means the literature measures a relevant part of the claim and a full biological verdict remains open. **Not assessable** means a recorded comparison has too much uncertainty for a verdict. The studies and their figures are linked in each row. [Literature review](claims/incoming/biological-evidence.md) · [Pump flux, charge and ATP measurements](claims/incoming/pump-charge-evidence.md) · [PGI worksheet audit](claims/incoming/pgi-evidence.md) · [Publisher’s PGI workbook and spectra](https://mdpi-res.com/metabolites/metabolites-02-00818/article_deploy/metabolites-02-00818-s001.zip)

Three measured rupture rates at each of two temperatures give FR-31 a disclosed comparison for first rupture. Evans and Smith describe an independent vesicle lifetime assay. Linking a particular constant-tension series to its vesicle sizes, exposure times and censoring remains open. A complete rupture returns each molecule to its destination in both assembly runners. [Rate measurements](claims/vesicle-lysis-threshold.md#biological-evidence) · [Independent study search](claims/incoming/vesicle-osmosis-evidence.md#independent-fixed-tension-series) · [Rupture receipts in Lean and Cells](claims/vesicle-lysis-returns.md) · [Independent translation-timing data screened by Search](claims/incoming/translation-release-evidence.md#fr-40-screening-for-independent-timing-data)

For a vesicle population at a common per-area hazard, survival at the mean area is a lower bound. The initial mean and actual area limits also give a sharp upper bound. In one synthetic mixture the bounds were 25% and 31.25%. Applying them to a preparation requires size data for the same starting cohort. [Vesicle survival bounds](claims/vesicle-area-survival.md)

## Maintaining the claims

Edit the claims register. A stable `id` gives each claim its note under `claims/`. Set `category` to a key from the register’s `categories` map. The key keeps the section link stable when its display title changes. In `formal.theorems`, map fully qualified Lean names to their source files. Use `uses` to link claims that build on earlier proofs. [Editable register](claims.json) · [JSON Schema](claims.schema.json)

Laws inherit the topic of their direct proofs. Use `law_categories` to put a law awaiting its first proof in the right section, or to choose its primary topic when proofs span several categories. Newly registered laws awaiting classification appear together in the overview.

In `formal.about`, list the canonical registry IDs whose law or operator property the theorem establishes. General composition and accounting theorems can leave this empty. In `numerical.comparisons`, list the comparison IDs for the claim. Each comparison names the models, laws and operators it exercised. For engine runs, `engine_revision` identifies the code that ran. The `record_revision` pins the comparison driver, the published result and any measured data files listed in `record_inputs`. The source audit also detects changes to those inputs. For a reference calculation this revision also pins the implementation. File paths in the register start at the checkout root.

In `biology.observable` and `unit`, name the quantity the claim needs. Use `biology.finding` for a brief published measurement, its scope and its primary citation. The generator puts that finding in the detailed catalog and the claim page. Formal experimental comparisons go in `biology.evidence`. The catalog reads their observed and predicted values, assessment and citation directly from those records. A claim awaiting measurements displays its requested observable.

The Search agent collects primary biological references in `claims/incoming/`, with the preparation, protocol, measured quantity, uncertainty and figure or table. The Lean lane checks the corresponding engine observable and records the comparison in the register. Enter a biological verdict when a comparison has a documented outcome. [Reviewed measurements and follow-up](PROGRESS.md#19-november-2026--biological-evidence-review) · [Channel voltage-clamp sources](claims/incoming/channel-gating-evidence.md)

A normal `lake build` checks that each named theorem exists in its declared module, then regenerates the topic overview, claim notes and catalog. With `CELLS_PYTHON` set to the Cells Python interpreter, the build also refreshes the registry inventory from the active checkout. A Lean-only build uses the last exported inventory. Commit the generated files alongside edits to the register. The documentation commands below run from `lean/`.

```bash
python3 scripts/generate_claims.py
python3 scripts/generate_claims.py --check
```

To compare with today's engine registrations, run the following in the Cells environment. Omit `--check` to refresh the inventory and pages. The inventory contains declaration IDs and locations exported by the engine. [Manifest source](../src/cells/registry/declarations.py#L659)

```bash
python -B scripts/generate_claims.py --live-registry --check
```

### Checking whether the engine code changed

The source check compares the working files with the Git blobs already pinned by each comparison. It reads the engine or reference sources, any tests and fixtures listed alongside them, and the comparison driver at its own evidence revision. It prints JSON naming every affected comparison, claim and path. Run it from `lean/` in a checkout containing the recorded history.

```bash
python3 -B scripts/generate_claims.py --check-sources
python3 -B scripts/generate_claims.py --check-sources --since 8f9bc050
```

The first command includes historical comparisons. The second checks for changes since the reviewed engine commit. Use the previous landing as the baseline in automation, or `HEAD` for uncommitted edits. Exit 0 means all selected files match, 1 means at least one changed, and 2 means the comparison could not be completed. A changed file identifies a driver to review or rerun. Imports and data omitted from a comparison's citations can also affect its result. A replay establishes the current numerical outcome. [Source review and retests](PROGRESS.md#claim-source-review)

These queries list claims with held-out measurements and claims whose comparison exercised a given law.

```bash
jq -r '.claims[] | select(any(.biology.evidence[]; .role == "held_out_from_fitting")) | .id' claims.json
jq -r --arg law 'logmean_electrodiffusion@1' '
  .comparisons as $checks | .claims[]
  | select(any(.numerical.comparisons[]; $checks[.].laws | index($law))) | .id' claims.json
```

### Reusing a proof

For new physics claims, look first for a compatible public theorem with matching assumptions and units. The charter gives the criteria for choosing a source, recording a direct import or optional comparison, and keeping a short proof local. [Cells Lean charter](AGENTS.md)

The single-site binding proof derives the Langmuir formula locally. For several forms and ligands, Physlib’s finite canonical ensemble gives each Cells form fraction at fixed free ligand activities. The binding claim also records how a magnesium–ATP affinity measured in one preparation performed in another. The face-power check imports the ATOMS Lab dimensional algebra. [One-site binding](claims/single-site-binding.md) · [Finite binding and ATP measurements](claims/binding-form-ensemble.md) · [Face-power example](claims/extracellular-face-dissipation.md)

The cleft-fill and wash proofs share the same ideal mixing term. Their default proof uses Mathlib’s logarithm bounds. An optional check identifies that term with Mathlib’s relative-entropy function. A second optional check imports Physlib’s two-state ensemble and recovers the equilibrium open probability of a junction gate when the fitted gate coordinate equals the dimensionless energy gap. [Cleft heat](claims/cleft-mixing-heat.md) · [Wash heat](claims/compartment-wash.md) · [Gate specialization](checks/physlib/JunctionEquilibrium.lean)

Two monotonicity proofs from `grn-lean` also apply directly to the scalar Hill factors in Cells. The optional check compiles the pinned definition and both upstream proofs, verifies the equivalence with our log-space evaluation, and shows that basal channel availability preserves the activating and inhibiting dose responses. The chemistry review records which reaction-network results apply to the closed enzyme fixture. [Hill specialization](checks/hill/Response.lean) · [Regulated channel proof](claims/regulated-state-response.md) · [Chemistry libraries tested against Cells](ENGINE_LAW_VERIFICATION.md#chemistry-libraries-tested-against-cells)

Three optional chemistry imports cover the closed enzyme reaction, conservation of a molecule exchanged with a finite pool, and the effect of lowering one activation barrier. Run `bash checks/chemistry/check.sh` from `lean/` with the pinned Lean on your path. The first run fetches the selected modules and their licenses. [Tested imports and future chemistry options](ENGINE_LAW_VERIFICATION.md#chemistry-imports-for-cells) · [Cells proofs](checks/chemistry/Reuse.lean)

## Build

Run these commands from `lean/`. Lean and Mathlib are pinned to 4.19.0. Lake reads the dependency revisions from the lockfile. The Linux x86-64 setup below reuses the lane’s installed compiler, or fetches it on a fresh checkout. [Lean release](https://github.com/leanprover/lean4/releases/tag/v4.19.0) · [Mathlib release](https://github.com/leanprover-community/mathlib4/releases/tag/v4.19.0)

```bash
mkdir -p .lake/bootstrap .lake/tmp .lake/cache
export TMPDIR="$PWD/.lake/tmp" XDG_CACHE_HOME="$PWD/.lake/cache"
if [ ! -x .lake/bootstrap/lean-4.19.0-linux/bin/lake ]; then
  curl -fL --retry 2 -o .lake/bootstrap/lean-4.19.0-linux.tar.zst \
    https://github.com/leanprover/lean4/releases/download/v4.19.0/lean-4.19.0-linux.tar.zst &&
    tar --zstd -xf .lake/bootstrap/lean-4.19.0-linux.tar.zst -C .lake/bootstrap
fi
export PATH="$PWD/.lake/bootstrap/lean-4.19.0-linux/bin:$PATH"
```

On the first build, fetch the compiled dependencies for the imported modules. Subsequent edits normally need only `lake build`.

```bash
lake exe cache get Mathlib.Data.Complex.Exponential \
  Mathlib.Probability.ProbabilityMassFunction.Binomial \
  Mathlib.Analysis.SpecialFunctions.Log.Basic Mathlib.Algebra.Order.BigOperators.Group.Finset \
  Mathlib.Analysis.Calculus.Deriv.Add Mathlib.Analysis.Calculus.Deriv.Inv \
  Mathlib.Data.Nat.Factorial.Basic Mathlib.Data.Matrix.Mul Mathlib.Tactic.Positivity \
  Mathlib.Analysis.Calculus.Deriv.MeanValue Mathlib.Analysis.Calculus.Deriv.Pow \
  Mathlib.Analysis.SpecialFunctions.ExpDeriv \
  Mathlib.Algebra.BigOperators.Fin Mathlib.Algebra.BigOperators.Field Mathlib.Data.List.Rotate \
  Mathlib.Algebra.Order.BigOperators.GroupWithZero.List \
  Mathlib.Tactic.FieldSimp Mathlib.Tactic.Linarith Mathlib.Tactic.Ring \
  Mathlib.Algebra.BigOperators.Group.Finset.Piecewise \
  Mathlib.Algebra.BigOperators.Group.Finset.Sigma \
  Mathlib.Algebra.BigOperators.Ring.Finset Mathlib.Data.Real.Basic Mathlib.Tactic.DeriveFintype
lake build
```

To check the ATOMS Lab dimensional algebra on the Cells toolchain, run the following from `lean/`. The first run downloads two source modules and their license from a pinned revision and fetches the compiled matrix-rank dependency if needed. Later runs can use the local cache. The check covers face power, electrode work and the Faraday conversion from molar flux to current. [Optional proofs](checks/units/FacePower.lean) · [Pinned source and compatibility edit](checks/units/check.sh)

```bash
bash checks/units/check.sh
```

For the relative-entropy comparison, the first command fetches the additional compiled Mathlib modules on the Cells pin. The second checks that the mixing term is nonnegative and vanishes exactly at a concentration ratio of one. [Optional proof](checks/mixing/KLFun.lean)

```bash
lake exe cache get Mathlib.InformationTheory.KullbackLeibler.KLFun
lake env lean -DwarningAsError=true checks/mixing/KLFun.lean
```

For the Hill proofs, the first run fetches two pinned source files, their MIT license and any missing compiled real-power dependencies. The command works from the cache on subsequent runs. [Hill proof runner](checks/hill/check.sh)

```bash
bash checks/hill/check.sh
```

<details>
<summary>Optional Physlib checks for a junction gate and finite binding</summary>

Physlib v4.22.0 uses the module name `PhysLean` and its own Lean 4.22.0 toolchain. Its extra axiom `Constants.kBAx` supplies a positive Boltzmann constant in the chosen units. From `lean/`, clone the tagged source once into `.lake/`. Run the commands inside that clone with Lean and Lake 4.22.0 on your path. [Upstream two-state ensemble](https://github.com/leanprover-community/physlib/blob/559b0e14bd87896d4ee536a536a8fb65e83b77cc/PhysLean/StatisticalMechanics/CanonicalEnsemble/TwoState.lean#L26-L37) · [Boltzmann constant axiom](https://github.com/leanprover-community/physlib/blob/559b0e14bd87896d4ee536a536a8fb65e83b77cc/PhysLean/StatisticalMechanics/BoltzmannConstant.lean#L20-L30) · [Gate specialization](checks/physlib/JunctionEquilibrium.lean)

```bash
gate_proof="$PWD/checks/physlib/JunctionEquilibrium.lean"
git clone --depth 1 --branch v4.22.0 https://github.com/leanprover-community/physlib .lake/physlib-v4.22.0
(
  set -e
  cd .lake/physlib-v4.22.0
  test "$(git rev-parse HEAD)" = 559b0e14bd87896d4ee536a536a8fb65e83b77cc
  lake env lean --version
  lake exe cache get Mathlib.Analysis.Calculus.ParametricIntegral \
    Mathlib.Analysis.SpecialFunctions.Log.Summable Mathlib.MeasureTheory.Integral.Prod \
    Mathlib.MeasureTheory.Measure.ProbabilityMeasure Mathlib.Analysis.InnerProductSpace.Basic \
    Mathlib.Analysis.Calculus.Deriv.Inv Mathlib.Data.NNReal.Defs Mathlib.Lean.Expr.Basic \
    Mathlib.Tactic.FieldSimp Mathlib.Tactic.Ring Mathlib.Algebra.BigOperators.Field \
    Mathlib.Algebra.BigOperators.Group.Finset.Sigma
  lake build PhysLean.StatisticalMechanics.CanonicalEnsemble.TwoState
  lake env lean -DwarningAsError=true "$gate_proof"
)
bash checks/physlib/binding.sh
```

</details>

## CPU comparisons

Run these from `lean/` with the pinned Lake executable on your path. Use the Cells CPU Python environment, or set `CELLS_PYTHON` to its interpreter. Each driver prints its numerical results as JSON. See the [development results](PROGRESS.md).

```bash
mkdir -p .lake/tmp .lake/cache
export TMPDIR="$PWD/.lake/tmp" XDG_CACHE_HOME="$PWD/.lake/cache"
export PYTHONPATH="../src:.." PYTHONDONTWRITEBYTECODE=1
export JAX_PLATFORMS=cpu JAX_ENABLE_X64=1 JAX_ENABLE_COMPILATION_CACHE=0
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
cells_python=${CELLS_PYTHON:-python}
```

<details>
<summary>Commands for individual comparisons</summary>

Run the OL5 comparison for single-event osmotic energies, short reaction products and measured vesicle deflation. Select one calculation with `--case energy`, `--case draws`, `--case deflation` (Bhatia) or `--case intact-deflation` (Fujiwara and Yanagisawa). The release check reads the saved diagnostic events and the matching final or lysis rows in four runs. Pass `--output DIRECTORY` to retain its bundles. [Energy proof](claims/vesicle-event-energy.md) · [Release proof](claims/vesicle-lysis-returns.md) · [OL5 replay differences](PROGRESS.md#ol5-six-replays)

```bash
"$cells_python" -B checks/vesicle_events.py
"$cells_python" -B checks/vesicle_release.py
```

For rupture at birth, the six-run comparison covers the followed daughter, its unfollowed sister and population slot reuse. Use `--population-record DIRECTORY` to check the shear and lysis rows in an existing population bundle. [R10 proof and archived OL5 result](PROGRESS.md#vesicle-birth-returns)

```bash
"$cells_python" -B checks/vesicle_birth.py
```

For mitochondrial respiration and ATP delivery, check the seven reaction columns, charge on each side and the material booked in a world with a finite matrix and intermembrane space. The results link complex I proton measurements and a bovine ATP synthase structure to the counts the model assumes. [Mitochondrial balance and measurements](PROGRESS.md#mitochondrial-cycle-accounting)

```bash
"$cells_python" -B checks/mitochondrial_cycles.py
```

Check the stall conditions of all seven cycles, compare instantaneous heat and flux with the independent component equations on both CPU backends, and reproduce the yeast synthase load comparison. [Thresholds, measurements and limits](PROGRESS.md#mitochondrial-stall-heat)

```bash
"$cells_python" -B checks/mitochondrial_stall.py
```

Check how free magnesium shifts the adenylate kinase equilibrium, how pH shifts the held reductant supply's stall, and how the tissue books material, work and heat. The comparison includes two kinase assays and a measured redox equilibrium. [Predictions and biological evidence](PROGRESS.md#mitochondrial-kinase-supply)

```bash
"$cells_python" -B checks/mitochondrial_reactions.py
```

For the conditioned kidney-cell voltage, check the two-dose extrapolation on three synthetic Na/K/Cl membranes and reproduce the fixed C3 prediction and its figure-reading bounds. [C3 results](PROGRESS.md#conditioned-voltage-bounds)

```bash
"$cells_python" -B checks/conditioned_voltage.py
```

For cell compartments and membrane recycling, follow each owner's species and lumen voltage, then compare how much membrane area and channel cargo return. The strict command checks whether an engine run can observe a nearly depleted channel population. It exits 1 on the recorded engine revision. [Compartment and recycling results](PROGRESS.md#owned-compartment-inventory) · [Reachable zero-count refusal](PROGRESS.md#trafficking-empty-surface)

```bash
"$cells_python" -B checks/compartment_trafficking.py
"$cells_python" -B checks/compartment_trafficking.py --require-trajectory
```

For division, compare the daughter amounts, voltage and booked work to the event equations. The same driver follows linear and exponential bridge closure, checks the resulting species fluxes, and compares both aperture curves with held-out points from a zebrafish bridge. [Division event](PROGRESS.md#isopotential-division) · [Bridge closure and measured diameters](PROGRESS.md#daughter-bridge-closure)

```bash
"$cells_python" -B checks/division_bridge.py
```

For membrane populations, follow precursor into maturing, active and removed units, then read the potassium flow at several patch areas. The driver also evaluates published receptor retention and endplate currents. The second command isolates the recorded rounding residual at exactly zero units. [Turnover and maturation](PROGRESS.md#surface-population-turnover) · [Current and surface count](PROGRESS.md#membrane-population-flow) · [Empty-population finding](PROGRESS.md#empty-surface-flow)

```bash
"$cells_python" -B checks/population_units.py
"$cells_python" -B checks/population_units.py --require-empty
```

For scheduled cell replacement, compare simultaneous donor and template arrivals, including a volume-preserving copy with nonzero water free energy. The second command checks that v2 admits the first representable template volume strictly inside the water bound and refuses the bound itself. [Material and charge](PROGRESS.md#scheduled-cell-replacement) · [Water and measured cell volumes](PROGRESS.md#cell-replacement-water) · [Boundary reproducer](PROGRESS.md#cell-replacement-volume-boundary) · [Repair and retest](PROGRESS.md#claim-source-review)

```bash
"$cells_python" -B checks/cell_replacement.py
"$cells_python" -B checks/cell_replacement.py --boundary-only --require-interior
```

For size-triggered fission and daughter continuation, compare fixed-quota and independent partitions, then follow empty and full daughters through the engine. The driver also compares measured bead-count variance with the probability model. To verify the figure readings, run `pdftocairo -f 3 -l 3 -svg article.pdf figure.svg` on the four-page PDF listed as `vector_pdf` and pass `--figure-svg figure.svg` to the driver. [Partition results and measurements](PROGRESS.md#size-threshold-fission) · [Daughter selection](PROGRESS.md#lineage-daughter-continuation) · [Ledger documentation finding](PROGRESS.md#lineage-fission-sink-sign) · [Figure source](checks/data/fornell2017_partition.json)

```bash
"$cells_python" -B checks/lineage_fission.py
```

For serial transfer and shear fission, follow an impermeant tracer through successive washes and from each parent to its daughters. The driver also checks discarded material, signed free energy and refused splits. The biological records include measured wash recovery and paired parent–daughter fluorescence. [Transfer results](PROGRESS.md#vesicle-serial-transfer) · [Division results](PROGRESS.md#vesicle-shear-fission)

```bash
"$cells_python" -B checks/vesicle_population.py
```

For the finite-compartment wash, the dilution checks cover neutral tracer, retained sites and the whole-wash resolution limit. The ion check compares three half washes with three 3/7 washes. It reports the public runner’s verdict and exits with status 1 when unchanged ions have unequal counters or the run is refused. For the two-gate junction, compare all gate-kind pairings with the constant-voltage expansion. [Wash counters](claims/wash-ion-counters.md) · [Tracer dilution](claims/compartment-wash.md) · [Series gates](PROGRESS.md#nov21-features)

```bash
"$cells_python" -B checks/compartment_wash.py
"$cells_python" -B checks/compartment_wash.py --case dilution
"$cells_python" -B checks/compartment_wash.py --case ion-counters
"$cells_python" -B checks/junction_series_gates.py
```

For scheduled pool replacement, replay both sides of the pulse and wash, including species receipts and saved relations. The capacity comparison exits 1 when either schedule accepts an oversized bath. [Tracer and energy results](PROGRESS.md#pool-replacement) · [Capacity finding](PROGRESS.md#pool-replacement-capacity)

```bash
"$cells_python" -B checks/pool_replacement.py --case pulse
"$cells_python" -B checks/pool_replacement.py --case capacity
```

For partial withdrawal, replay the host balance, finite-word edge cases, sample moments and measured bead fractions. To verify all 180 plotted counts, export page 3 of the cited vector PDF with `pdftocairo -svg -f 3 -l 3 paper.pdf fig2.svg` and add `--figure-svg fig2.svg`. The energy check compares all five fields and the saved ledger, including rare midpoint draws. The matched-buffer proof bounds the mean heat per starting molecule by ln(n+1)/n on the exact sampling grid. [Matched-buffer result](PROGRESS.md#matched-buffer-heat) · [Energy results](PROGRESS.md#fr35-withdrawal-energy) · [Count data and source](checks/data/pool_withdrawal_measurements.json)

```bash
"$cells_python" -B checks/pool_withdrawal.py
"$cells_python" -B checks/pool_withdrawal_energy.py
"$cells_python" -B checks/matched_buffer.py
```

For vesicle exchange, compare lipid insertion and neutral solute permeation against their rate equations and measured washout and swelling. The shared-pool controls follow one lipid and one solute between two vesicles. The one-event fixed-volume case now returns the declared-lumen records. [Measurements and engine results](PROGRESS.md#vesicle-permeation) · [Shared-pool counts](PROGRESS.md#shared-pool-inventory) · [Earlier reporting failure](PROGRESS.md#shared-pool-declared-volume) · [Repair and retest](PROGRESS.md#claim-source-review)

```bash
"$cells_python" -B checks/vesicle_exchange.py
"$cells_python" -B checks/shared_pool.py --controls-only
"$cells_python" -B checks/shared_pool.py --declared-only
```

For bilayer vesicles, the driver compares two molecular area units, the osmotic volume and membrane tension with a 70-digit reference. The repaired engine agrees on all eight threshold decisions. The driver also compares measured deflation, swelling and survival during fixed-tension holds. [Physical results](PROGRESS.md#bilayer-footprint) · [Earlier threshold finding](PROGRESS.md#vesicle-threshold-hold) · [Repair and measured rupture timing](PROGRESS.md#biological-model-review)

```bash
"$cells_python" -B checks/vesicle.py --controls-only
"$cells_python" -B checks/vesicle.py
```

For a restricted cleft, the controls follow tracer dilution and mixing heat through membrane growth and a 60:40 patch split. The full comparison also tests a positive trace concentration on each side. It exits with status 1 when the engine refuses a valid fill. [Geometry, tracer measurements and heat finding](PROGRESS.md#cleft-bath-fill)

```bash
"$cells_python" -B checks/restricted_lumen.py --controls-only
"$cells_python" -B checks/restricted_lumen.py
```

For the held bath, follow the controller’s dose and the tissue’s supply through four solution changes, then compare potassium reversal shifts with measured cardiac currents. The full comparison verifies that both entry orders preserve an intended trace dose. The second command runs the ordinary controls. [Bath accounting and biological evidence](claims/scheduled-bath-exchange.md) · [Recipe-order repair and retest](PROGRESS.md#bath-order-repair)

```bash
"$cells_python" -B checks/bath_schedule.py
"$cells_python" -B checks/bath_schedule.py --controls-only
```

For regulated availability, pulse and wash out a ligand in both operator versions and compare the channel response with rat SK2 dose and timing measurements. The full driver also checks the order of reporter production when turnover changes its own regulator. The midpoint repair restored second-order convergence on the four tested grids. The controls-only run checks the pulse, both rate samples and the SK2 calculation. [Channel proof and biological measurements](claims/regulated-state-response.md) · [Turnover finding and reproducer](claims/regulated-turnover-routing.md)

```bash
"$cells_python" -B checks/regulated_availability.py
"$cells_python" -B checks/regulated_availability.py --controls-only
"$cells_python" -B checks/regulated_availability.py --ramp-only
```

For scheduled turnover, the driver checks production, clearance and chemical work, then compares a neuronal protein chase and a chamber with independently metered flow. The full run also checks that both extreme-rate worlds retain the 1 fmol net change and its chemical work. The second command runs the ordinary controls. [Proof, measurements and engine finding](claims/scheduled-species-turnover.md)

```bash
"$cells_python" -B checks/species_turnover.py
"$cells_python" -B checks/species_turnover.py --controls-only
```

For saturable uptake, compare the finite extracellular pool and both recipient cells against an independent solution, then test the concentration response against human red-cell measurements. [Proof and measured rates](claims/saturable-species-exchange.md)

```bash
"$cells_python" -B checks/species_exchange.py
```

The site driver follows two binding populations and their shared free ligand. The electrode driver compares both pulse polarities with independent charge and work calculations. The mixed-ion driver resolves the three currents at zero total current and reconstructs three measured squid-axon voltage shifts. [Site occupancy](claims/site-occupancy-stages.md) · [Electrode pulses](claims/electrode-pulses.md) · [Mixed membrane](claims/mixed-ion-reversal.md)

```bash
"$cells_python" -B checks/site_occupancy.py
"$cells_python" -B checks/current_injection.py
"$cells_python" -B checks/mixed_membrane.py
```

For membrane insertion, compare both operators with a one-patch fixed-charge solution. The first command reports the engine result and exits with status 1 if any case fails. The two optional controls rerun the stress case with known single-patch heat and image-charge values substituted in memory. Both repaired operators now complete the original stress rollout. [Driver](checks/membrane_insertion.py) · [Original result](PROGRESS.md#19-november-2026--membrane-insertion-heat) · [Repair](PROGRESS.md#nov21-engine-review)

```bash
"$cells_python" -B checks/membrane_insertion.py
"$cells_python" -B checks/membrane_insertion.py --one-patch-control heat
"$cells_python" -B checks/membrane_insertion.py --one-patch-control heat-and-charge
```

For single-site binding, compare the compiled law against the independent S1 states and read the occupied fraction in a tissue cell. The input substitution checks whether the comparison distinguishes free and total ligand. [Binding driver](checks/single_site_binding.py)

```bash
"$cells_python" -B checks/single_site_binding.py
```

For finite binding, compare the fractions of every form in S1–S7 at fixed free ligand concentrations, then check a two-ligand tissue read, isomer multiplicity and the cross-study Mg–ATP prediction. [Ensemble comparison](checks/binding_ensemble.py) · [Measurement inputs](checks/data/mgatp_binding.json)

```bash
"$cells_python" -B checks/binding_ensemble.py
```

For the inverse binding problem, the first command checks uniqueness, the second checks the finite directions that decide feasibility for the registered chemistries, and the third reproduces the float64 sign failures near zero. The third command exits with status 1 while those failures remain. [Equilibrium and measured endpoints](claims/binding-equilibrium-unique.md) · [Finite direction tests](claims/binding-margin-vertices.md) · [Signed-total cases](claims/binding-equilibrium-feasibility.md)

```bash
"$cells_python" -B checks/binding_equilibrium.py
"$cells_python" -B checks/binding_vertices.py
"$cells_python" -B checks/binding_feasibility.py
```

For Hill activation and inhibition, compare the compiled Cells factors with a 65-digit evaluation of the upstream formula on the engine's reaction test grid. [Hill comparison](checks/hill/compare.py)

```bash
"$cells_python" -B checks/hill/compare.py
```

For junction transport, the driver compares fluxes with an independent scalar reference and runs the per-cell potassium ledger on one closed tissue world. Reversing the endpoint bookings tests the sensitivity of the per-cell comparison. [Junction driver](checks/constant_field.py) · [Independent reference](../validation/tissue/surface_reference.py#L71)

```bash
"$cells_python" -B checks/constant_field.py
"$cells_python" -B -m pytest -q -p no:cacheprovider \
  ../tests/unit/test_surface_transport.py::test_independent_surface_laws_and_accounting \
  ../tests/unit/test_surface_transport.py::test_patch_subdivision_route_reversal_and_padding \
  ../tests/unit/test_surface_transport.py::test_equilibrium_and_transport_blocking
```

For voltage-dependent junction gating, compare the clamped trajectory at both polarities, then follow tracer transfer in three tissue cell pairs through a block and release. [Gate comparison](checks/junction_gate.py) · [Cx43 clamp measurements](claims/incoming/junction-gate-evidence.md)

```bash
"$cells_python" -B checks/junction_gate.py
```

The Na⁺/K⁺ driver checks the eight gated channels and both leaks together on one tissue membrane. The chloride driver checks the sign of material transfer, electrode current and the shift in reversal voltage. A third calculation applies published voltage-clamp protocols to Kv1.1, Kv1.4 and NaV1.2. [Na⁺/K⁺ comparison](checks/ion_channels.py) · [Chloride comparison](checks/chloride_channel.py) · [Experimental conditions and measured currents](claims/incoming/channel-gating-evidence.md)

```bash
"$cells_python" -B checks/ion_channels.py
"$cells_python" -B checks/chloride_channel.py
"$cells_python" -B checks/channel_clamp_evidence.py
```

The direct tissue clamp is checked against the independent current formula. The separate composite check compares the scheduled and effective controls, then tests the public clamp against the ordinary observed current and a second voltage. It exits with status 1 while that public comparison is unavailable or disagrees. [Tissue current and measured conducting fractions](claims/clamped-channel-current.md) · [Composite clamp retest](PROGRESS.md#d272-wash-clamp-retests)

```bash
"$cells_python" -B checks/clamped_channel_current.py
"$cells_python" -B checks/clamped_channel_current.py --composite
"$cells_python" -B checks/channel_density.py
"$cells_python" -B checks/kv15_ph.py
```

For neutral permeation, compare the compiled inward flux and the final amounts in a closed tissue pair with the analytic solution. The unequal-volume case distinguishes amount from concentration. [Neutral driver](checks/neutral_permeation.py) · [Closed-pair reference](../validation/passive/passive_reference.py#L66)

```bash
"$cells_python" -B checks/neutral_permeation.py
```

For charged permeation, compare the CPU flux, heat and slopes with 60-digit arithmetic, follow charge through a finite tissue pair, and reproduce the two experimental current–voltage comparisons. [Charged-route driver](checks/charged_permeation.py)

```bash
"$cells_python" -B checks/charged_permeation.py
```

For proton leak, check the reversal voltage, instantaneous heat, the small-voltage branch and the free H⁺ read in a buffered tissue cell. The driver also resolves the polynomial’s reversal ratio at 80-digit precision. [Proton driver](checks/proton_leak.py) · [Flux reference](../validation/betse/junction_transport/check.py#L10)

```bash
"$cells_python" -B checks/proton_leak.py
"$cells_python" -B checks/ims_proton_leak.py
```

For ATP-driven transport, compare compiled tissue rates against the four frozen proton and neutral cargo panels. The driver reports free energy, cycle flux, heat and work errors, then checks the voltage response and both off switches. It also finds the proton pump's stall voltage for each of the eight yeast vacuole assay conditions at all four supported couplings. [ATP driver](checks/atp_cycle.py) · [Tissue results](PROGRESS.md#19-november-2026--atp-driven-transport) · [Vacuole results](PROGRESS.md#biological-model-review)

```bash
"$cells_python" -B checks/atp_cycle.py
```

For the Na⁺/K⁺ and calcium pumps, compare both stall voltages and the outward current against independent scalar calculations. One of the five cells starts with cancelling pump currents. The 1 ms tissue run checks all three ion transfers and the heat booked by each pump. [Driver](checks/electrogenic_pumps.py) · [Results](PROGRESS.md#19-november-2026--sodium-potassium-and-calcium-pump-charge)

```bash
"$cells_python" -B checks/electrogenic_pumps.py
```

For extracellular faces, run the direction and power cases and the closed tissue model. The driver checks the engine's two mean thresholds, opposing drives, an adjacent-float pair and an intentionally reversed flux. The reference test checks the scalar mean against Decimal. [Face driver](checks/logmean_face.py) · [Scalar reference](../validation/tissue/surface_reference.py#L13)

```bash
"$cells_python" -B checks/logmean_face.py
"$cells_python" -B -m pytest -q -p no:cacheprovider \
  ../tests/unit/test_surface_reference.py::test_reference_logarithmic_mean_against_decimal
```

For closed reactions, the driver reads the declaration, checks its correspondence to Lean and runs the registered operator with the fixture’s time-zero controls. It compares all four stored species changes with the booked extents, then measures both inventory residuals at the existing tolerances for stored amounts. [Enzyme driver](checks/closed_enzyme.py) · [Tolerance definitions](../tests/unit/test_species_reactions_halfstep.py#L275)

```bash
"$cells_python" -B checks/closed_enzyme.py
"$cells_python" -B -m pytest -q -p no:cacheprovider \
  ../tests/unit/test_species_reactions_halfstep.py::test_the_bookings_are_exact_on_random_states \
  '../tests/unit/test_species_reactions_refusals.py::test_definition_refusals[unbalanced]'
```

For assembly exchange, compare entry and exit rates at every three-species composition through eight molecules. Two seeded lineages check the heat and material booked through growth, division and loss of the last molecule. The driver also compares the first species’ share during growth with equal and unequal leave constants. [Assembly driver](checks/reservoir_exchange.py) · [Results and lipid measurements](PROGRESS.md#19-november-2026--assembly-reservoir-exchange)

```bash
"$cells_python" -B checks/reservoir_exchange.py
```

For the original GARD laws, compare both directions of each transfer and each four-event cycle against exact rational rates. The full run also exercises two cases where subtracting a large diagonal coefficient loses the remaining catalyst. It exits with status 1 when the passive law refuses a valid event. The controls-only command runs the ordinary comparisons and two passing one-event controls. [Driver](checks/gard_catalysis.py) · [Findings and membrane measurements](PROGRESS.md#19-november-2026--gard-catalysis-on-reversible-transfers)

```bash
"$cells_python" -B checks/gard_catalysis.py
"$cells_python" -B checks/gard_catalysis.py --controls-only
```

For FR-31, run the four synthetic cohort-size checks. The FR-38 commands compare point releases and interval counters, then run three compiled RNA worlds with marks in [2, 4) and [6, 8) s. The replay saves half-second observations and compares reconstruction on half-second and two-second grids. The last command checks FR-42 in the labelled and unlabelled tissue, tests its finite-step math on NumPy and CPU JAX, and recalculates the paired Actn1 fractions. [Area bounds](PROGRESS.md#fr31-area-bounds) · [Marked RNA windows](PROGRESS.md#fr38-marked-fates) · [Neutral tissue labels](PROGRESS.md#fr42-neutral-survival)

```bash
"$cells_python" -B checks/vesicle_area.py
"$cells_python" -B checks/vesicle_area.py --osmotic-evidence
"$cells_python" -B checks/arrival_windows.py --reference-only
"$cells_python" -B checks/arrival_windows.py
JAX_PLATFORMS=cpu "$cells_python" -B checks/arrival_survival.py
```

For the GARD v2 two-word cache, replay the reversible event, signed updates and precision guard. The separate range command checks an admitted finite-rate event, upper and lower exponent boundaries, and explicit capacity on both sides of 4,096. It exits with status 1 if any of its nine expectations fails. For templated polymerisation, check the two balances across every saved row of three compiled worlds, including two chains competing for one machine pool. [Cache precision](PROGRESS.md#gard-v2-cache) · [Repaired and historical range checks](PROGRESS.md#gard-v2-range-repair) · [Polymerisation balances and measurements](PROGRESS.md#polymerisation-balances)

```bash
"$cells_python" -B checks/gard_cache.py
"$cells_python" -B checks/gard_cache.py --range
"$cells_python" -B checks/polymerisation_balances.py
```

For a chain with a terminal RNA hold, check both machine-return policies as the completion-marking window closes and the durable fraction changes. The second command asks the public reader for both physical and marked RNA in two lossless controls. [Machine and residue balances](claims/polymerisation-machines.md) · [Four fate records](claims/release-fate-export.md)

```bash
"$cells_python" -B checks/terminal_release.py
"$cells_python" -B checks/terminal_release.py --lossless
```

On a Cells revision with the replacement fixture, run `python -m validation.gene_regulation.replace_restart --out NEW_DIRECTORY`. In the same Cells environment, `python checks/producer_replacement.py NEW_DIRECTORY/replace_restart.json` checks the saved counters and labels. Keep the JSON beside the run’s `checkpoint/` directory. [Results and public admission status](PROGRESS.md#fr38-producer-replacement)

For ideal and regular assembly mixing, one command checks the 592 registered probe states under both count measures and rebooks four compiled trajectories. It compares the activity curves with Shaw’s 25 DOPC measurements and Parker’s independent crystal-onset endpoint. [Driver](checks/assembly_mixing.py) · [Fit, assumptions and results](PROGRESS.md#19-november-2026--ideal-and-regular-assembly-mixing)

```bash
"$cells_python" -B checks/assembly_mixing.py
```

For stochastic encounters and transition-state catalysis, compare the two directional rates with and without the catalyst, then replay a two-state clock on the same random draws. The full run returns status 1 when an expected rate or clock fails. The controls-only run checks the ordinary pairs, boundary cases and two equivalent or well-conditioned clocks. The last command evaluates the confined-binding measurements using the engine’s pool reaction. [Clock reproducer](checks/assembly_kinetics.py) · [Measured occupancies](PROGRESS.md#19-november-2026--stochastic-encounters-and-transition-state-catalysis) · [Opposed-contact clock retest](PROGRESS.md#claim-source-review)

```bash
"$cells_python" -B checks/assembly_kinetics.py
"$cells_python" -B checks/assembly_kinetics.py --controls-only
"$cells_python" -B checks/confined_binding.py
```

The inward-rectifier driver checks the current–voltage slope, equivalent concentration normalizations and Kir4.1 currents at matched driving voltage. All three normalizations now produce the same current, transfer and heat. The symport driver checks all four sodium counts and compares the two-sodium carrier with measured charge, particle flux and voltage shifts. [Original experimental comparisons](PROGRESS.md#19-november-2026--inward-rectification-and-sodium-anion-symport) · [Retest of all six numerical findings](PROGRESS.md#six-numerical-retests)

```bash
"$cells_python" -B checks/inward_rectifier.py
"$cells_python" -B checks/inward_rectifier.py --controls-only
"$cells_python" -B checks/sodium_anion_symport.py
```

For the eight-state two-sodium carrier, compare each edge with an independent stationary master equation and test the predicted dose response against measured propionate currents. The full run also checks whether the diagnostic flux agrees with the material flux down to 10⁻³⁰² fmol/s capacity and at zero. The original extreme-capacity case passes on the repaired engine. [Proof and biological comparison](claims/sodium-anion-diagram.md) · [Repair verification](PROGRESS.md#sodium-anion-capacity-repair)

```bash
"$cells_python" -B checks/sodium_anion_diagram.py
"$cells_python" -B checks/sodium_anion_diagram.py --controls-only
```

For the potassium–anion operator, compare a closed two-compartment run with the exact concentration trajectory. The full comparison checks admission of the coarse step and finite chemical affinity and heat at extreme concentration ratios. The second command runs the smaller-step controls. [Original result](PROGRESS.md#19-november-2026--potassium-and-anion-cotransport) · [Overflow repair and retest](PROGRESS.md#potassium-affinity-repair)

```bash
"$cells_python" -B checks/potassium_anion_symport.py
"$cells_python" -B checks/potassium_anion_symport.py --controls-only
```

For water and potassium–anion transport in changing volumes, compare the CPU engine with two independent numerical integrators. The second command checks vesicle swelling, red-cell volumes, pressure-driven flow and the water change accompanying measured solute transfer in trout red cells. [Proof, experiments and numerical results](claims/osmotic-water.md)

```bash
"$cells_python" -B checks/osmotic_water.py
"$cells_python" -B checks/osmometry.py
```

For the tissue balance, the driver follows A and B through one 50 ms composite step on twelve finite extracellular compartments. It compares the change in their stored amounts at nodes 2 through 5 with the signed transfers on the two boundary faces. Each species also has to account for its share of the local conversion. The same comparison runs on the full chain and with the largest boundary face reversed in the recorded transfers. The existing passive-chain test checks the trajectory against the independent split-step reference. [Regional driver](checks/regional_balance.py) · [Reference comparison](../tests/unit/test_species_reactions_composition.py#L84)

```bash
"$cells_python" -B checks/regional_balance.py
"$cells_python" -B -m pytest -q -p no:cacheprovider \
  '../tests/unit/test_species_reactions_composition.py::test_guard_2_linear_networks_on_the_chain_run_the_engine_orders_map[passive]'
```

</details>
