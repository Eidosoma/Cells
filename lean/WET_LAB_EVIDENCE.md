<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Paired wet-lab evidence

Each row names one Cells assumption and two public primary experimental records. A supporting pair requires independently collected data from separate research groups and a comparable observable. Direction, approximate scale and pointwise numerical agreement are identified separately. A study may inform several rows. The linked claim page identifies calibration data and gives the full biological verdict.

| Outcome | Reviewed pairs |
| --- | ---: |
| Supported by both studies | 10 |
| Challenged by both studies | 1 |
| Different experimental results | 1 |
| Comparison unresolved | 3 |
| Independent replication unconfirmed | 2 |

## Supported by both studies

| Assumption and claim | Measurements and scope | Independence and sources |
| --- | --- | --- |
| <a id="pair-pgi-reversal"></a>Phosphoglucose isomerase can convert G6P to F6P or F6P to G6P, depending on the starting mixture. [Deterministic reactions stall at equilibrium and dissipate free energy](claims/rate-equation-flux.md#biological-evidence) | F6P fell by 3.787 mM in the F6P-start extract series and rose by 1.172 mM in the G6P-start series. The purified enzyme approached F6P/G6P ≈ 0.30 from both sides. Both assays support the direction of conversion. Instantaneous dissipation remains unmeasured. | Eicher’s group measured cell-extract time courses by NMR. Dyson and Noltmann independently assayed purified rabbit-muscle enzyme. [Eicher et al. (2012), Fig. 5](https://doi.org/10.3390/metabo2040818) · [Dyson and Noltmann (1968), Table I and Fig. 13](https://doi.org/10.1016/S0021-9258(18)93559-3) |
| <a id="pair-adenylate-kinase-magnesium"></a>The apparent adenylate-kinase equilibrium quotient formed from total nucleotides depends on free Mg²⁺. [Magnesium shifts the apparent equilibrium of adenylate kinase](claims/mitochondrial-adenylate-kinase.md#biological-evidence) | The first assay gave 0.391 at zero free Mg²⁺ and 1.05 at 1 mM. The maize assay reported a span of 0.30–1.27 across 0.0014–8.3 mM and 0.76 ± 0.10 at 1.8–1.9 mM. Both resolve dependence on Mg²⁺. They leave the position of the Cells maximum and its transfer to heart mitochondria open. | Lawson and Veech measured a myokinase preparation. Kleczkowski and Randall measured their own purified maize-leaf enzyme. [Lawson and Veech (1979)](https://pubmed.ncbi.nlm.nih.gov/36398/) · [Kleczkowski and Randall (1991)](https://doi.org/10.1093/jxb/42.4.537) |
| <a id="pair-complex-i-protons"></a>Forward bovine complex I translocates about four protons per pair of electrons. [Restoring both respiratory carriers fixes the turnover ratio and outward charge](claims/mitochondrial-respiratory-balance.md#biological-evidence) | Galkin measured 4.00 ± 0.05 H⁺/2e⁻ from proton and NADH rates. Jones obtained 4.21 ± 0.15, 4.10 ± 0.17 and 4.02 ± 0.19 from three flux comparisons on the same four preparations. This constrains complex I. The complete three-complex charge cycle remains unmeasured here. | The Moscow and Cambridge groups prepared their own bovine heart submitochondrial particles and used different assays. [Galkin et al. (1999), Fig. 2 and Eq. 3](https://doi.org/10.1016/S0014-5793(99)00575-X) · [Jones et al. (2017), Table 3 and Fig. 3](https://doi.org/10.1074/jbc.M116.771899) |
| <a id="pair-popc-urea-permeability"></a>Urea crosses a protein-free POPC membrane down its concentration gradient, with comparable apparent permeability in influx and efflux assays. [Neutral solute entry scales with area and spherical washout with inverse radius](claims/vesicle-permeation.md#biological-evidence) | The reported efflux estimate converts to 0.0129 µm/s at 22 °C. The influx estimate was 0.013 ± 0.001 µm/s at 0.10 and 0.20 M. Central values differ by under 1%. Both coefficients were inferred from optical data. Curvature, temperature reporting and error conventions limit transfer of a single fitted value. Permeability is an input to Cells. | Brändén’s group recorded washout from tethered nanovesicles. Peterlin’s group followed individual giant vesicles taking up urea. [Brändén et al. (2010), Fig. 3A](https://doi.org/10.1016/j.bpj.2010.03.059) · [Peterlin et al. (2012), Fig. 6a](https://doi.org/10.1039/C1SM06670F) |
| <a id="pair-vesicle-deflation-direction"></a>Increasing external osmolarity reduces the enclosed volume of intact, solute-loaded vesicles. [Membrane area caps the volume that minimizes a vesicle’s osmotic free energy](claims/osmotic-vesicle-volume.md#biological-evidence) | Fujiwara’s final/initial volume was about 0.25 (70/285 = 0.246). Viallat reported radius shrinking from 25 to 17 µm, giving a spherical volume fraction of 0.314 (50/162 = 0.309). Its apparent area fell by about half. The direction is reproduced. Conservation of membrane area and individual retained-solute counts remain open. | Fujiwara and Yanagisawa followed five DOPE/DOPC liposomes. Viallat’s group independently tracked a spherical DOPC vesicle during slow titration. [Fujiwara and Yanagisawa (2014), ACS Synthetic Biology](https://doi.org/10.1021/sb4001917) · [Viallat et al. (2004), Fig. 2](https://doi.org/10.1016/S0006-3495(04)74277-0) |
| <a id="pair-cold-red-cell-sugar-affinity"></a>Early 3-O-methylglucose influx into sugar-depleted human erythrocytes is half-saturated near 1–2 mM under cold conditions. [Saturable uptake from a finite pool conserves neutral solute](claims/saturable-species-exchange.md#biological-evidence) | Sage’s fitted Kₘ was 1.4 ± 0.2 mM, and Klepper’s control gave 1.3 mM across 0.3–6 mM with no Kₘ uncertainty reported. Cells uses two Sage points for calibration (1.19 mM). The separate donor supports the concentration scale. Absolute capacity, long-time depletion and transfer between two cells remain open. | Sage and Carruthers measured three independent experiments on ice. Klepper’s group measured its own healthy donor four times per concentration at 4 °C. [Sage and Carruthers (2014), Fig. 2A](https://doi.org/10.1152/ajpcell.00044.2014) · [Klepper et al. (2001), Fig. 3B–C and Table 1](https://doi.org/10.1016/S0014-5793(01)02463-2) |
| <a id="pair-red-cell-sugar-saturation"></a>Initial 3-O-methylglucose influx saturates with increasing extracellular sugar in intact human erythrocytes on ice and at 15 °C. [Saturable uptake from a finite pool conserves neutral solute](claims/saturable-species-exchange.md#biological-evidence) | Batt’s influx Kₜ values were 5.0 and 6.1 mM, compared with 1.4 ± 0.2 mM on ice in Sage. Both studies resolve saturation. A single Kₘ across these conditions would miss the 15 °C values. Preparation and assay differences confound attribution to temperature alone. | Batt and Schachter measured two blood specimens at 15 °C. Sage and Carruthers collected a separate cold series, also used in the cold-affinity comparison. [Sage and Carruthers (2014), Fig. 2A](https://doi.org/10.1152/ajpcell.00044.2014) · [Batt and Schachter (1973), Table V](https://doi.org/10.1172/JCI107350) |
| <a id="pair-proton-reversal-ph"></a>The reversal voltage of a selective proton current shifts with the free pH gradient in the Nernst direction. [The local free proton concentration at each buffered endpoint sets leak reversal](claims/buffered-proton-reversal.md#biological-evidence) | The three mitoplast groups reversed at means of −62.2, −91.1 and +28.8 mV at outside-minus-inside pH differences of +1, +1.5 and −0.5. The alveolar tail-current reversal shifted in the same direction by about 52 mV per pH unit over four units. The shared result concerns the zero-current voltage. Permeability and gating remain separate questions. | Bertholet’s group recorded mouse skeletal-muscle mitoplasts. Cherny’s group recorded rat alveolar epithelial cells with a different proton pathway. [Bertholet et al. (2019), Nature 571, 515–520](https://doi.org/10.1038/s41586-019-1400-3) · [Cherny et al. (1995), Fig. 2](https://doi.org/10.1085/jgp.105.6.861) |
| <a id="pair-smct-propionate-saturation"></a>Human SMCT1 substrate-induced current saturates as external propionate increases at −50 mV. [The eight-state sodium–anion carrier shares a cycle flux and saturates with external substrate](claims/sodium-anion-diagram.md#biological-evidence) | The published half-saturation concentrations were 127 ± 14 and 162 ± 26 µM. The dose responses independently support saturation and an affinity scale around 0.1–0.2 mM. The exact affinity, eight transition rates and sodium coupling ratio remain separate questions. | Miyauchi’s and Paroder’s groups recorded their own oocytes expressing human SMCT1. [Miyauchi et al., Fig. 2A](https://doi.org/10.1074/jbc.C400059200) · [Paroder et al. (2006), Fig. 3C](https://doi.org/10.1073/pnas.0602365103) |
| <a id="pair-hypertonic-water-efflux"></a>A hyperosmotic external bath draws water out of protein-free phospholipid vesicles. [Water potential sets flow, heat and osmometric equilibrium](claims/osmotic-water.md#biological-evidence) | Both experiments detected shrinkage by dye quenching. Their fitted DOPC/POPC water permeabilities were 15.8/13.0 at 30 °C and 16.0/12.0 at 20 °C, in 10⁻³ cm/s. Flow direction is the shared prediction. Lipid ordering constrains mobility inputs and heat was unmeasured. | Mathai’s and Frallicciardi’s groups performed separate stopped-flow experiments. Only the latter paper’s experimental panels are used. [Mathai et al. (2008), Fig. 1A and Table I](https://doi.org/10.1085/jgp.200709848) · [Frallicciardi et al. (2022), Figs. 1A, 3A and 4A](https://doi.org/10.1038/s41467-022-29272-x) |

## Challenged by both studies

| Assumption and claim | Measurements and scope | Independence and sources |
| --- | --- | --- |
| <a id="pair-vesicle-resting-radius-cap"></a>The optically measured relaxed radius is a hard cap on spherical vesicle size during hypotonic swelling before rupture. [Membrane area caps the volume that minimizes a vesicle’s osmotic free energy](claims/osmotic-vesicle-volume.md#biological-evidence) | An initially full, inextensible sphere predicts zero further swelling. Shibly saw mean volume rises of 1.7 ± 0.1% and 2.6 ± 0.1% (14 and 17 vesicles). Chabanon’s closed pre-pore optical traces rose above the estimated relaxed radius. Both challenge using resting optical geometry as the cap. Available membrane area, slack and elastic dilation were not separately measured in both assays. | Shibly’s group transferred DOPC vesicles to mildly hypotonic glucose. Chabanon’s group tracked POPC vesicles during a stronger hypotonic challenge. [Shibly et al. (2016), Fig. 2B](https://doi.org/10.1016/j.bpj.2016.09.043) · [Chabanon et al. (2017), Fig. 1c–d](https://doi.org/10.1016/j.bpj.2017.03.018) |

## Different experimental results

| Assumption and claim | Measurements and scope | Independence and sources |
| --- | --- | --- |
| <a id="pair-smct-propionate-stoichiometry"></a>Each human SMCT1 cycle imports two Na⁺ per propionate. [Sodium coupling sets net charge and the stall voltage of an anion carrier](claims/sodium-anion-symport.md#biological-evidence) | Gopal reported 2.7 ± 0.2 net positive charges per propionate. With monovalent propionate and fully coupled current that implies 3.7 ± 0.2 Na⁺ per substrate. Coady measured 2.3 ± 0.3 Na⁺ per propionate from paired shifts in zero-current voltage (n = 7, SEM). Uncoupled current and passive propionic-acid uptake affect the inference. The two assays give different estimates for this substrate. | Gopal’s and Coady’s groups studied human SMCT1 in separate oocyte experiments. Coady is the source of the Cells two-sodium choice. [Gopal et al. (2004), Fig. 9B](https://doi.org/10.1074/jbc.M405365200) · [Coady et al. (2007), Figs. 1, 2 and 4](https://doi.org/10.1529/biophysj.107.108555) |

## Comparison unresolved

| Assumption and claim | Measurements and scope | Independence and sources |
| --- | --- | --- |
| <a id="pair-xc0-native-oocyte-charge"></a>The sum of independently measured mobile and fixed charge in a native oocyte equals its capacitive charge. [Rounding and rejection of the initial charge balance](claims/xc0-charge-anchor.md#biological-evidence) | Guizouarn reported Na/K/Cl means of 30.0/115.2/21.2 mM, a pooled water estimate of about 500 nL per oocyte and a group voltage of −56.8 ± 1.5 mV. Costa estimated free-ion concentrations of 10.1/109.5/37.7 mM. Assay type and sampling differ. Evaluating charge closure requires total ion amounts, independently measured fixed charge, capacitance and voltage on the same cell. Neither series supplies that set. | Guizouarn’s group assayed its own control oocytes. Costa’s group measured a separate set with ion-selective electrodes. [Guizouarn et al. (2004), Table I, controls](https://doi.org/10.1074/jbc.M311920200) · [Costa et al. (1989), summary item 7](https://doi.org/10.1113/jphysiol.1989.sp017649) |
| <a id="pair-pgi-pair-closure"></a>G6P and F6P alone form a closed measured inventory throughout these enzyme assays. [Rosenbrock reaction steps preserve closed material inventories](claims/rosenbrock-inventory.md#biological-evidence) | The purified assay recovered 2.505 of the initial 2.500 mM at 30 min. Eicher’s dataset 2 lost 22.29% of the measured sum, while dataset 3 gained 1.04%. Recovery error and unmeasured species prevent treating the extract as a matched closed pool. These data cannot establish a failure of the integration invariant. | Kahana’s group assayed a partially purified preparation. Eicher’s group measured a separate cell extract capable of additional reactions. [Kahana et al. (1960), Table II, experiment B](https://doi.org/10.1016/S0021-9258(18)64594-6) · [Eicher et al. (2012), Fig. 5 and PGI worksheet](https://doi.org/10.3390/metabo2040818) |
| <a id="pair-vesicle-ideal-volume-transfer"></a>The retained-osmole volume ratio transfers quantitatively from freely suspended to adhered deflating vesicles. [Membrane area caps the volume that minimizes a vesicle’s osmotic free energy](claims/osmotic-vesicle-volume.md#biological-evidence) | Fujiwara’s plateau was about 0.25 versus 0.246 expected. At 58 mOsm/L the adhered example in Wolfisberg Fig. 2B gave reduced volume 0.30 versus 0.431 from prepared sucrose (0.439 from the first point). The authors report overall agreement across their 21-vesicle series in Fig. 3. Reduced volume depends on area, and a matched single-vesicle uncertainty is missing. | The Fujiwara and Wolfisberg groups used separate preparations. Wolfisberg’s illustrated vesicle and ensemble belong to one study. [Fujiwara and Yanagisawa (2014), ACS Synthetic Biology](https://doi.org/10.1021/sb4001917) · [Wolfisberg et al. (2025), Fig. 2B](https://doi.org/10.1021/jacs.5c13925) |

## Independent replication unconfirmed

| Assumption and claim | Measurements and scope | Independence and sources |
| --- | --- | --- |
| <a id="pair-mammalian-rotor-coupling"></a>Exactly three protons per ATP is the intrinsic tight-coupling ratio of the mammalian mitochondrial ATP synthases represented by the Cells model. [ATP synthesis and delivery return four charge equivalents in the declared three-proton model](claims/mitochondrial-atp-delivery.md#biological-evidence) | Both structures contain eight c-subunits. One proton per c-subunit and three ATP per turn imply 8/3 H⁺ per synthesized ATP, compared with 3 in Cells. The distinction concerns ideal rotor coupling. Effective proton cost under load or during ATP export requires flux measurements. | The sheep particles and cryo-EM density are new. The initial reconstruction and atomic fit used bovine 5ARA, which itself used Watt’s 2XND. Independence of the eight-subunit count from the starting model is unconfirmed. [Watt et al. (2010), Fig. 1 and Discussion](https://doi.org/10.1073/pnas.1011099107) · [Pinke et al. (2020), ovine cryo-EM structure 6TT7](https://doi.org/10.1038/s41594-020-0503-8) |
| <a id="pair-vacuolar-pump-low-ph"></a>The yeast vacuolar pump reversal exceeds +40 mV at cytosolic pH 7.5 and lumen pH 3.1. [Free energy sets ATP-driven transport direction and stall](claims/atp-cycle.md#biological-evidence) | The journal reports a lower bound of +40 mV for three vacuoles. The workshop reports +50 ± 8 mV with no replicate count, and its low-pH figure is a time trace at 0 mV. The values are compatible. The two publications cannot establish an independent replication. | The workshop and journal reports come from the same Kettner research group. An independent preparation or dataset lineage for the workshop value is undocumented. [Kettner et al. (2003), Fig. 3 and Table 2](https://doi.org/10.1016/S0006-3495(03)74789-4) · [Kettner, 2002 workshop proceedings (2003), Fig. 7B and Table 1](https://www.beilstein-institut.de/download/736/kettner_1.pdf#page=14) |

## Awaiting paired review

Claims with at least two datasets awaiting their first paired review (22). Several datasets can come from one paper or measure different quantities.

- [A closing daughter bridge scales flux by its remaining aperture](claims/daughter-bridge-closure.md#biological-evidence)
- [A finite-pool wash preserves assembly cargo and books the two bath energies](claims/pool-replacement.md#biological-evidence)
- [A moving binder carries its ligands across a face](claims/forms-face-carriage.md#biological-evidence)
- [Changing molecular area units preserves the exact vesicle rupture decision](claims/vesicle-lysis-threshold.md#biological-evidence)
- [Fluid from a held bath dilutes a growing cleft in proportion to its added volume](claims/cleft-bath-fill.md#biological-evidence)
- [Free and engaged polymerases or ribosomes sum to their machine pool](claims/polymerisation-machines.md#biological-evidence)
- [Hold work and release close the pore’s heat balance](claims/vesicle-pore-heat.md#biological-evidence)
- [Integer units at membrane-patch division](claims/fr43-integer-segregation.md#biological-evidence)
- [Ion charge sets permeation reversal and bounds the current–voltage slope](claims/charged-permeation.md#biological-evidence)
- [Lipid insertion scales with membrane area and diffusion-limited capture scales with radius](claims/vesicle-phase-exchange.md#biological-evidence)
- [Marked RNA is accounted for in both release fates, including after label reuse](claims/release-window-survival.md#biological-evidence)
- [Mitochondrial cycles reverse at zero free energy and dissipate power in either direction](claims/mitochondrial-stall-heat.md#biological-evidence)
- [Pair interactions change the energy of membrane entry with composition](claims/assembly-regular-mixing.md#biological-evidence)
- [Partial pool withdrawal conserves counts and fixes their conditional moments](claims/pool-withdrawal.md#biological-evidence)
- [Precursor molecules balance across maturation, surface insertion and removal](claims/surface-population-turnover.md#biological-evidence)
- [RNA keeps its producer label through export, cell replacement and return](claims/producer-replacement-rna.md#biological-evidence)
- [Replacement over water accounts for incoming volume and composition-dependent free energy](claims/cell-replacement-water.md#biological-evidence)
- [Returning membrane area can leave some of its channels in the receiving pool](claims/membrane-retrieval-recycling.md#biological-evidence)
- [Total ligand increases with its own free concentration](claims/binding-ligand-response.md#biological-evidence)
- [Tracer returns to a finite exterior pool after a wash](claims/fr47-shell-wash-recovery.md#biological-evidence)
- [Vesicle area variation bounds survival during a tension hold](claims/vesicle-area-survival.md#biological-evidence)
- [Whole-molecule counts set the ideal mixing cost of membrane entry](claims/assembly-ideal-mixing.md#biological-evidence)

## Seeking a second dataset

<details><summary>Claims with one recorded dataset (41)</summary>

- [A fixed-gate current curve identifies the product of channel abundance and availability](claims/clamped-channel-current.md#biological-evidence)
- [A held bath can return to its original composition after supplying solute and work to tissue](claims/scheduled-bath-exchange.md#biological-evidence)
- [A partial wash dilutes free tracer and preserves its inventory](claims/compartment-wash.md#biological-evidence)
- [A regulated channel approaches its held-dose plateau without overshoot](claims/regulated-state-response.md#biological-evidence)
- [A size-triggered division preserves each membrane species across both daughter records](claims/size-threshold-division.md#biological-evidence)
- [A two-region sample represents the chamber under proportional withdrawal or equal concentrations](claims/two-region-sampling.md#biological-evidence)
- [A wash collects free tracer while surface-bound tracer can release later](claims/wall-wash-retention.md#biological-evidence)
- [An inward membrane tube reduces the lumen inside a vesicle’s outer contour](claims/vesicle-deflation-geometry.md#biological-evidence)
- [At fixed channel drive, whole-patch flow tracks the surface unit count](claims/membrane-population-flow.md#biological-evidence)
- [Bilayer area is half the sum of the molecular footprints in its two leaflets](claims/bilayer-footprint.md#biological-evidence)
- [Charge carriers reconcile daughter volume and membrane shares at division](claims/isopotential-division.md#biological-evidence)
- [Chloride gradients set leak reversal and inward chloride carries positive outward current](claims/chloride-channel-charge.md#biological-evidence)
- [Each compartment belongs to one cell and its charge sets its lumen voltage](claims/owned-compartment-inventory.md#biological-evidence)
- [Finite binding forms have normalized Boltzmann weights](claims/binding-form-ensemble.md#biological-evidence)
- [Finite molecule counts set stochastic encounter rates and paired event heat](claims/assembly-stochastic-encounter.md#biological-evidence)
- [Identical donor traces under transfer and degradation have distinct receiver and loss records](claims/transfer-or-degradation.md#biological-evidence)
- [Independent channel counts determine relative availability from fixed-gate currents](claims/channel-density-availability.md#biological-evidence)
- [Junction conductance relaxes toward a voltage-dependent target](claims/junction-gate.md#biological-evidence)
- [Kv1.5 activation and current retention under extracellular acidification](claims/kv15-ph-activation.md#biological-evidence)
- [Label remaining in a closed cell and clearance since the pulse account for the original cohort](claims/regional-pulse-balance.md#biological-evidence)
- [Membrane voltage in kidney epithelial cells under condition C3](claims/rptec-voltage-c3.md#biological-evidence)
- [Neutral arrival-time cohorts share one physical loss rate](claims/fr42-cohort-shares.md#biological-evidence)
- [Neutral label fluxes add and labels can exchange across a face with zero parent flux](claims/neutral-label-diffusion.md#biological-evidence)
- [Potassium rectification sets reversal, dissipation and a bound on slope conductance](claims/inward-rectifier.md#biological-evidence)
- [Potassium–anion cotransport follows the concentration products in a closed pair](claims/potassium-anion-symport.md#biological-evidence)
- [Prescribed totals admit at most one binding equilibrium](claims/binding-equilibrium-unique.md#biological-evidence)
- [Production and first-order clearance preserve a positive pool and account for gross turnover](claims/scheduled-species-turnover.md#biological-evidence)
- [Rupture by the hold endpoint requires enough accumulated exposure](claims/vesicle-pore-clock.md#biological-evidence)
- [Serial transfer accounts for the spent bath and the vesicles removed](claims/vesicle-serial-transfer.md#biological-evidence)
- [Shear fission partitions the parent among all daughters and books discarded siblings](claims/vesicle-shear-fission.md#biological-evidence)
- [Simultaneous replacement books the old and arriving species, charge and electrical work](claims/scheduled-cell-replacement.md#biological-evidence)
- [Size-triggered fission conserves each species under fixed-quota and independent partitions](claims/size-threshold-fission.md#biological-evidence)
- [Stage exits account for residues in unfinished, terminally held and detached chains](claims/polymerisation-residues.md#biological-evidence)
- [The held reductant supply has a pH-dependent stall and balances work in either direction](claims/mitochondrial-reductant-supply.md#biological-evidence)
- [Three passive ions set one zero-current membrane voltage](claims/mixed-ion-reversal.md#biological-evidence)
- [Two processes spending and replenishing one finite pool](claims/fr43-shared-writers.md#biological-evidence)
- [Vesicle pore rates scale with area and increase on warming](claims/vesicle-pore-rate.md#biological-evidence)
- [Vesicles withdrawing from a finite shared bath conserve each species across the population](claims/shared-pool-inventory.md#biological-evidence)
- [Voltage and free proton concentrations set the leak reversal](claims/proton-leak.md#biological-evidence)
- [Which ligand totals admit a positive binding equilibrium?](claims/binding-equilibrium-feasibility.md#biological-evidence)
- [Zero outer current preserves combined matrix and intermembrane-space charge](claims/mitochondrial-combined-charge.md#biological-evidence)

</details>
