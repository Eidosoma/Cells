# Cells proofs

This Lean library connects engine laws to their proofs, numerical checks and experimental measurements. Each claim page records the assumptions and links to the code and sources.

## Biological evidence

The last column below gives the experimental result and what it can test. **Partial evidence** means the literature measures a relevant part of the claim and a full biological verdict remains open. **Not assessable** means a recorded comparison has too much uncertainty for a verdict. The studies and their figures are linked in each row. [Literature review](claims/incoming/biological-evidence.md) · [Pump flux, charge and ATP measurements](claims/incoming/pump-charge-evidence.md) · [PGI worksheet audit](claims/incoming/pgi-evidence.md) · [Publisher’s PGI workbook and spectra](https://mdpi-res.com/metabolites/metabolites-02-00818/article_deploy/metabolites-02-00818-s001.zip)

## Proof index

<!-- generated: claims-index -->

| Claim | Lean proof | Numerical check | Biological measurements and limits |
| --- | --- | --- | --- |
| [Reversing a junction reverses its flux](claims/junction-flux-reversal.md) | Proved | Checked | **Partial evidence.** A single Cx43 channel carried about −5 pA at −50 mV and +4.8 to +4.95 pA at +50 mV in symmetric salt. This checks reversal of electrical current. Reversal of one ion’s flux under exchanged concentrations remains open. [Wang and Veenstra, Fig. 1](https://pubmed.ncbi.nlm.nih.gov/9101407/) |
| [At equal voltage, junction flux follows the concentration gradient](claims/junction-concentration-gradient.md) | Proved | Checked | **Partial evidence.** Near zero junction voltage, a charged tracer moved from the loaded cell to its neighbor. A separate study estimated 226 ± 75 calcein molecules/s per Cx26 channel at a 125 μM gradient, with only the donor voltage-clamped during transfer. [Palacios-Prado and Bukauskas, Fig. 2B](https://pmc.ncbi.nlm.nih.gov/articles/PMC2736430/) · [Zonta et al., Fig. 1A–C](https://doi.org/10.1186/1478-811X-11-15) |
| [A blocked junction carries zero flux](claims/junction-blocking.md) | Proved | Checked | **Partial evidence.** Heptanol suppressed junctional current in a bovine epithelial cell pair, and the current returned after washout. The trace has no reported detection threshold for residual ion flux. [Wang et al., Fig. 2E–F](https://pubmed.ncbi.nlm.nih.gov/20089928/) |
| [Junction conductance relaxes toward a voltage-dependent target](claims/junction-gate.md) | Proved | Checked | **Partial evidence.** Seven wild-type Cx43 cell pairs gave residual conductances of 0.35 ± 0.01 and 0.33 ± 0.01 relative to the prepulse at positive and negative voltages. At −100 mV the same decay had two time constants, 70 ± 5 and 931 ± 54 ms (SEM). The Cells reference parameters give one time constant of 50.0 ms. The experiment leaves exact transient polarity symmetry and the independent availability multiplier open. [Sahu and Bera, Table 2 and Fig. S2](https://pmc.ncbi.nlm.nih.gov/articles/PMC3607587/) |
| [Passive neutral solute follows its concentration gradient](claims/neutral-permeation.md) | Proved | Checked | **Partial evidence.** Urea flux was measured over time in liposomes of three lipid compositions. Comparing a Cells rate requires the gradient, area and permeability for the same preparation. [Lande et al., Fig. 3](https://doi.org/10.1085/jgp.106.1.67) |
| [Voltage and free proton concentrations set the leak reversal](claims/proton-leak.md) | Proved | Checked | **Partial evidence.** In Jurkat T cells the proton-current reversal shifted −47 mV per pH unit, versus an ideal −58 mV per pH unit. The fitted slope uncertainty and intracellular pH limit a quantitative verdict. [Schilling et al., Fig. 2E](https://doi.org/10.1113/jphysiol.2002.028878) |
| [Free energy sets ATP-driven transport direction and stall](claims/atp-cycle.md) | Proved | Checked | **Partial evidence.** In yeast vacuoles at cytosolic pH 8.5 and vacuolar pH 5.0, measured reversal was −17.5 ± 5 mV (SE, six trials). The tightly coupled two-proton prediction was −86.5 mV. The authors proposed a proton shunt. Vesicles showed ATP-dependent riboflavin uptake. Neutral-cargo reversal and voltage independence remain open. [Kettner et al., Table 2](https://pmc.ncbi.nlm.nih.gov/articles/PMC1303676/) · [Van Herwaarden et al., Fig. 3E](https://pmc.ncbi.nlm.nih.gov/articles/PMC1800714/) |
| [Stall voltages and net charge of the sodium–potassium and calcium pumps](claims/electrogenic-pump-charge.md) | Proved | Checked | **Partial evidence.** Squid axons gave 3.05 ± 0.13 Na⁺ per net charge from −60 to −90 mV in Na-free seawater and 2.72 ± 0.09 at 0 mV with 390 mM external Na⁺ (SEM). Cells predicts 3. Red-cell ghosts lost about 3 Na⁺ per ATP. In pig-brain calcium pumps, separate rate measurements imply 1.02 Ca²⁺ per ATP and about +1.4 net charges per ATP after inward H⁺ is included. Cells counts +2 from Ca²⁺ alone. The simulated stall voltages still lack a matched measurement. [Rakowski et al., Table I](https://doi.org/10.1085/jgp.93.5.903) · [Garrahan and Glynn](https://doi.org/10.1113/jphysiol.1967.sp008297) · [Salvador et al., Table I](https://doi.org/10.1074/jbc.273.29.18230) |
| [Extracellular face flux follows the electrochemical potential drop](claims/extracellular-face-direction.md) | Proved | Checked | **Partial evidence.** Diluting NaCl on opposite sides of a claudin-2 pore shifted its current-reversal voltage in opposite directions. Reversal of an individual ion’s net flux remains unmeasured. [Weber et al., Fig. 6A–B](https://elifesciences.org/articles/09906) |
| [Passive extracellular face transport dissipates energy](claims/extracellular-face-dissipation.md) | Proved | Checked | **Partial evidence.** Trout gill epithelia supplied two-way sodium tracer flux and voltage measurements. Active transport contributed to the measured flux, so passive heat production cannot be inferred from these data alone. [Galvez et al., Fig. 3 and Tables 1–2](https://www.zoology.ubc.ca/~woodcm/Woodblog/wp-content/uploads/2016/07/Galvez-et-al.-2008-In-Vitro-Cell.pdf) |
| [Edge orientation preserves each compartment’s transfer balance](claims/transfer-orientation.md) | Proved | Checked | **Partial evidence.** Paired clamp recordings showed equal and opposite junctional currents. Calibrated gain and loss of the same ion in both cells remain unmeasured. [Wang and Veenstra, Fig. 1A and C](https://pubmed.ncbi.nlm.nih.gov/9101407/) |
| [Only boundary transfers change a region’s inventory during transport](claims/transfer-inventory.md) | Proved | Checked | **Partial evidence.** Perfused rat hearts lost 139 ± 12 μmol of K⁺ per g dry weight in effluent over 40 min. Tissue depletion was measured in separate hearts, leaving the within-heart balance open. [Kuki et al., Figs. 3–4](https://doi.org/10.1161/01.RES.67.2.401) |
| [Balanced reactions preserve a weighted inventory](claims/reaction-inventory.md) | Proved | Checked | **Partial evidence.** The measured G6P + F6P pool fell 0.613357 mM (7.31%) in the first of five time courses. The raw acquisition lists 0.950 mL and different timing from the workbook. Volumes, shared calibration and unobserved pools limit the amount balance. [Eicher et al., Fig. 5](https://www.mdpi.com/2218-1989/2/4/818) · [Publisher’s workbook](https://mdpi-res.com/metabolites/metabolites-02-00818/article_deploy/metabolites-02-00818-s001.zip) |
| [Binding and catalysis conserve enzyme and substrate](claims/enzyme-inventories.md) | Proved | Checked | **Partial evidence.** NMR resolved ligand states bound to triosephosphate isomerase. Testing both balances requires simultaneous amounts of free enzyme, substrate, bound complex and product during turnover. [Rozovsky and McDermott, Figs. 3–5](https://pmc.ncbi.nlm.nih.gov/articles/PMC1794347/) |
| [One-site binding follows the free ligand concentration](claims/single-site-binding.md) | Proved | Checked | **Partial evidence.** For oxygen binding to human myoglobin at 10 °C, two digitized points set the affinity. The other three gave a root-mean-square error of 0.0422 in fractional occupancy. All five come from one figure with unknown pointwise uncertainty. [Rossi-Fanelli and Antonini, Fig. 2](https://pubmed.ncbi.nlm.nih.gov/13584010/) · [Digitized points](https://bi1.caltech.edu/2017/code/t05_nonlinear_regression.html) |
| [Uncharged membrane insertion dissipates nonnegative capacitor heat](claims/membrane-insertion-heat.md) | Proved | Failed | **Partial evidence.** Capacitance steps were measured during secretion in chromaffin cells. Testing insertion heat also needs the initial charge of the added membrane and independent electrical work and energy measurements. [Neher and Marty](https://doi.org/10.1073/pnas.79.21.6712) |
| [Regional inventory changes by net boundary transfer across a split step](claims/regional-reaction-transport.md) | Proved | Checked | **Partial evidence.** A perfused rat liver study followed labeled carbon in tissue, perfusate, bile and CO₂. Reconstructing the balance requires matched time intervals, sample volumes and coverage of the other tissue pools. [Fausto, Fig. 1](https://doi.org/10.1042/bj1290811) |
| [Membrane voltage in kidney epithelial cells under condition C3](claims/rptec-voltage-c3.md) | Open | Checked | **Not assessable.** Observed -18 mV. Predicted -14.59 mV. The retrospective C3 prediction was 3.41 mV above the figure reading. The closeout records a descriptive result. Biological acceptance remains unresolved because experimental uncertainty and the recording boundary are insufficiently characterized. [Bonzanni et al. (2020)](https://doi.org/10.1242/bio.048553) |

<!-- /generated -->

Each numerical result applies to the cases in its linked record. The coverage table lists the registered laws and operators that have a direct theorem or appear in an engine comparison. [Engine law coverage](COVERAGE.md) · [Design notes](ENGINE_LAW_VERIFICATION.md) · [Voltage pilot closeout](../reports/BIO003_PILOT_CLOSEOUT.md)

## Maintaining the claims

Edit the claims register. A stable `id` gives each claim its note under `claims/`. In `formal.theorems`, map fully qualified Lean names to their source files. Use `uses` to link claims that build on earlier proofs. [Editable register](claims.json) · [JSON Schema](claims.schema.json)

In `formal.about`, list the canonical registry IDs whose law or operator property the theorem establishes. General composition and accounting theorems can leave this empty. In `numerical.comparisons`, list the comparison IDs for the claim. Each comparison names the models, laws and operators it exercised. For engine runs, `engine_revision` identifies the code that ran. The `record_revision` pins the comparison driver and the published result. For a reference calculation it also pins the implementation. File paths in the register start at the checkout root.

In `biology.observable` and `unit`, name the quantity the claim needs. Use `biology.finding` for a brief published measurement, its scope and its primary citation. The generator puts that finding in the README and the claim page. Formal experimental comparisons go in `biology.evidence`. The index reads their observed and predicted values, assessment and citation directly from those records. A claim awaiting measurements displays its requested observable.

The research agent collects candidate papers in `claims/incoming/`. The November review identifies what each assay measured, which claim it can address and what is needed for a quantitative comparison. Enter a biological verdict in the register when a comparison has a documented outcome. [Reviewed measurements and follow-up](PROGRESS.md#19-november-2026--biological-evidence-review)

A normal `lake build` checks that each named theorem exists in its declared module, then regenerates the index, claim notes and coverage table. With `CELLS_PYTHON` set to the Cells Python interpreter, the build also refreshes the registry inventory from the active checkout. A Lean-only build uses the last exported inventory. Commit the generated files alongside edits to the register. The documentation commands below run from `lean/`.

```bash
python3 scripts/generate_claims.py
python3 scripts/generate_claims.py --check
```

To compare with today's engine registrations, run the following in the Cells environment. Omit `--check` to refresh the inventory and pages. The inventory contains declaration IDs and locations exported by the engine. [Manifest source](../src/cells/registry/declarations.py#L659)

```bash
python -B scripts/generate_claims.py --live-registry --check
```

These queries list claims with held-out measurements and claims whose comparison exercised a given law.

```bash
jq -r '.claims[] | select(any(.biology.evidence[]; .role == "held_out_from_fitting")) | .id' claims.json
jq -r --arg law 'logmean_electrodiffusion@1' '
  .comparisons as $checks | .claims[]
  | select(any(.numerical.comparisons[]; $checks[.].laws | index($law))) | .id' claims.json
```

### Reusing a proof

Keep the Cells theorem beside the mechanism it explains. Import a narrow upstream module when it fits our pinned Lean version. For a short result from another Lean version, a local derivation can be simpler. When copying licensed source, keep the original attribution, license and required notices with the copy. Give the claim a `formal.sources` entry for the upstream theorem at a fixed revision and label how we used it. The binding claim shows a local Lean 4 derivation. The face-power claim links an optional external import. [Binding example](claims/single-site-binding.md) · [Face-power example](claims/extracellular-face-dissipation.md)

Two monotonicity proofs from `grn-lean` also apply directly to the scalar Hill factors in Cells. The optional check compiles the pinned definition and both upstream proofs, then verifies the equivalence with our log-space evaluation. The chemistry review records which reaction-network results apply to the closed enzyme fixture. [Hill specialization](checks/hill/Response.lean) · [Chemistry libraries tested against Cells](ENGINE_LAW_VERIFICATION.md#chemistry-libraries-tested-against-cells)

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
  Mathlib.Analysis.SpecialFunctions.Log.Basic Mathlib.Algebra.Order.BigOperators.Group.Finset \
  Mathlib.Tactic.FieldSimp Mathlib.Tactic.Linarith Mathlib.Tactic.Ring \
  Mathlib.Algebra.BigOperators.Group.Finset.Piecewise \
  Mathlib.Algebra.BigOperators.Group.Finset.Sigma \
  Mathlib.Algebra.BigOperators.Ring.Finset Mathlib.Data.Real.Basic Mathlib.Tactic.DeriveFintype
lake build
```

To check the ATOMS Lab dimensional algebra on the Cells toolchain, run the following from `lean/`. The first run downloads two source modules and their license from a pinned revision and fetches the compiled matrix-rank dependency if needed. Later runs can use the local cache. The check compiles the dimension of flux × molar potential and checks the scalar conversion used by the engine. [Optional proof](checks/units/FacePower.lean) · [Pinned source and compatibility edit](checks/units/check.sh)

```bash
bash checks/units/check.sh
```

For the Hill proofs, the first run fetches two pinned source files, their MIT license and any missing compiled real-power dependencies. The command works from the cache on subsequent runs. [Hill proof runner](checks/hill/check.sh)

```bash
bash checks/hill/check.sh
```

## CPU comparisons

Run these from `lean/` with the pinned Lake executable on your path. Use the Cells CPU Python environment, or set `CELLS_PYTHON` to its interpreter. Each driver prints its numerical results as JSON. See the [development results](PROGRESS.md).

```bash
mkdir -p .lake/tmp .lake/cache
export TMPDIR="$PWD/.lake/tmp" XDG_CACHE_HOME="$PWD/.lake/cache"
export PYTHONPATH="../src:.." PYTHONDONTWRITEBYTECODE=1
export JAX_PLATFORMS=cpu JAX_ENABLE_X64=1 JAX_ENABLE_COMPILATION_CACHE=0
cells_python=${CELLS_PYTHON:-python}
```

For membrane insertion, compare both operators with a one-patch fixed-charge solution. The first command reports the engine result and exits with status 1 if any case fails. The two optional controls rerun the stress case with known single-patch heat and image-charge values substituted in memory. At the recorded revision the original and heat-only runs fail, and the heat-and-charge control completes. [Driver](checks/membrane_insertion.py) · [Results](PROGRESS.md#19-november-2026--membrane-insertion-heat)

```bash
"$cells_python" -B checks/membrane_insertion.py
"$cells_python" -B checks/membrane_insertion.py --one-patch-control heat
"$cells_python" -B checks/membrane_insertion.py --one-patch-control heat-and-charge
```

For single-site binding, compare the compiled law against the independent S1 states and read the occupied fraction in a tissue cell. The input substitution checks whether the comparison distinguishes free and total ligand. [Binding driver](checks/single_site_binding.py)

```bash
"$cells_python" -B checks/single_site_binding.py
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

For neutral permeation, compare the compiled inward flux and the final amounts in a closed tissue pair with the analytic solution. The unequal-volume case distinguishes amount from concentration. [Neutral driver](checks/neutral_permeation.py) · [Closed-pair reference](../validation/passive/passive_reference.py#L66)

```bash
"$cells_python" -B checks/neutral_permeation.py
```

For proton leak, check the reversal voltage, instantaneous heat, the small-voltage branch and the free H⁺ read in a buffered tissue cell. The driver also resolves the polynomial’s reversal ratio at 80-digit precision. [Proton driver](checks/proton_leak.py) · [Flux reference](../validation/betse/junction_transport/check.py#L10)

```bash
"$cells_python" -B checks/proton_leak.py
```

For ATP-driven transport, compare compiled tissue rates against the four frozen proton and neutral cargo panels. The driver reports free energy, cycle flux, heat and work errors, then checks the voltage response and both off switches. [ATP driver](checks/atp_cycle.py) · [Numerical and biological results](PROGRESS.md#19-november-2026--atp-driven-transport)

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

For the tissue balance, the driver follows A and B through one 50 ms composite step on twelve finite extracellular compartments. It compares the change in their stored amounts at nodes 2 through 5 with the signed transfers on the two boundary faces. Each species also has to account for its share of the local conversion. The same comparison runs on the full chain and with the largest boundary face reversed in the recorded transfers. The existing passive-chain test checks the trajectory against the independent split-step reference. [Regional driver](checks/regional_balance.py) · [Reference comparison](../tests/unit/test_species_reactions_composition.py#L84)

```bash
"$cells_python" -B checks/regional_balance.py
"$cells_python" -B -m pytest -q -p no:cacheprovider \
  '../tests/unit/test_species_reactions_composition.py::test_guard_2_linear_networks_on_the_chain_run_the_engine_orders_map[passive]'
```
