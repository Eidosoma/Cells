# Xenopus bioelectric cancer lane: an external review

*Received 19 November 2026 from an external reviewer, who read the repository at b546c99d. It is
checked in as received, except for three changes: this title, a personal link to the full brief
replaced by a note, and tracking parameters removed from the source links. The lead's gap analysis
and the user's priority ruling (D225) follow separately.*

## Recommendation

**Create a dedicated Xenopus bioelectric cancer lane, starting with the 2013 local tumor-suppression experiments, then extending to distant tissue effects, gap-junction organization, and delayed optogenetic treatment.** The Xenopus visualization can become the front end for that lane, showing recorded voltage, transport, and biological responses at the cell and tissue scales.

Cells already has much of the required electrochemical foundation. The principal additions are **specific transporter and actuator laws, calibrated downstream biological responses, and—later—the growth and tissue mechanics needed to model an established lesion.**

I reviewed the repository for this purpose at commit [`b546c99d`](https://github.com/Eidosoma/Cells/tree/b546c99d615a1fa8ff611e49ff272337f334d5f2), dated 19 November 2026, and researched the relevant primary papers.

**Full implementation brief:** XENOPUS_BIOELECTRIC_CANCER_LANE.md, held by the user, not in the repository.

The brief contains the proposed experiments, source bibliography, engine integration points, calibration and evaluation split, acceptance criteria, visualization specification, and first implementation bundle.

---

## 1. What the Cells review changes about the plan

### The existing architecture is suitable for the physical core

The useful foundation is `resolved_pump_tissue@3`, composed through `resolved_pump_composite@1`. Its ion inventories, membrane and extracellular potentials, channel fluxes, junctions, and explicit reservoirs provide the right starting point.

The particularly valuable recent addition is the **general membrane-transporter infrastructure**. A sodium-coupled butyrate transporter can be introduced through a declared transport cycle with explicit species, stoichiometry, membrane orientation, and energy accounting. That gives this lane a route into the existing engine without creating a separate Xenopus simulator. See the [transporter implementation](https://github.com/Eidosoma/Cells/blob/b546c99d615a1fa8ff611e49ff272337f334d5f2/src/cells/kinds/transporter.py) and [cycle forms](https://github.com/Eidosoma/Cells/blob/b546c99d615a1fa8ff611e49ff272337f334d5f2/src/cells/laws/cycles/forms.py).

However, several distinctions matter:

| Requirement | What Cells currently provides | What this lane must add or qualify |
|---|---|---|
| Electrical state and ion transport | Membrane voltage, ion inventories, electrochemical transport, extracellular domains | A preparation calibrated to the relevant Xenopus cell type and developmental stage |
| Butyrate transport | General carrier-cycle infrastructure | A sodium/monocarboxylate law with independently sourced kinetics |
| Biological signaling | Reaction and regulatory-state infrastructure | The particular mediator-to-HDAC/cell-response model |
| Chemical movement | Routes, exchange, turnover, and reaction operators | Correct treatment of charged solutes and the required operator combinations |
| Tumor growth and invasion | Prescribed division and bounded vertex mechanics | State-dependent proliferation, survival, material supply, and appropriate movement/topology changes |
| Optogenetic treatment | General electrical mechanisms and controls | Light-dependent kinetics and, for Arch, explicit optical energy and proton accounting |
| Visualization | Species data, shared run views, replay adapters | Xenopus preparation metadata and views of this lane’s actual records |

The current species reaction/exchange machinery has restrictions around neutral species and composition. **Butyrate and serotonin should not be declared electrically neutral simply to make a configuration run.** The carrier and species mechanisms need to represent their physical roles correctly. Those constraints are visible in the [species operators](https://github.com/Eidosoma/Cells/blob/b546c99d615a1fa8ff611e49ff272337f334d5f2/src/cells/operators/species_reactions.py) and [regulatory feedback implementation](https://github.com/Eidosoma/Cells/blob/b546c99d615a1fa8ff611e49ff272337f334d5f2/src/cells/operators/species_regulated_availability.py).

### The existing cancer lane is relevant infrastructure, but a different scientific target

You already have a substantial [gap-junction cancer replication lane](https://github.com/Eidosoma/Cells/blob/b546c99d615a1fa8ff611e49ff272337f334d5f2/docs/GAP_JUNCTION_CANCER_REPLICATION.md) for the 2026 Grodstein–Mathews–Levin preprint. That work concerns a **miR200/ZEB state switch and connexin-dependent communication**.

The proposed Xenopus lane should reuse its evidence conventions, physical primitives, and suitable tooling. Its EMT switch should not automatically become the biological explanation for the earlier Xenopus experiments.

There is also an existing [Xenopus physiology candidate](https://github.com/Eidosoma/Cells/blob/b546c99d615a1fa8ff611e49ff272337f334d5f2/validation/betse/biological_candidates/xenopus_costa_1989.json). It is explicitly marked unvalidated and unrunnable. Its underlying study concerns **oocytes**, which makes it useful for a bounded physiology benchmark, but not a parameter set for every embryo or tadpole cell. [pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/2600847/)

My assessment here is based on source and recorded project evidence; I did not rerun the qualification suite.

---

## 2. The Levin papers to organize the lane around

The literature separates into **two biological systems**:

1. **Oncogene-induced tumor-like structures**, usually abbreviated ITLS.
2. **Instructor-cell effects on melanocytes**, including pigmentation, proliferation, morphology, and migration.

They should have separate models and endpoints.

### A. Local tumor suppression: Chernet and Levin, 2013

**“Transmembrane voltage potential is an essential cellular parameter for the detection and control of tumor development in a Xenopus model.”**

This is the best first target. The study connects oncogene-associated electrical changes with local hyperpolarizing interventions and a proposed **SLC5A8–butyrate–HDAC pathway**. For Xrel3, the reported 1.54-fold and 1.62-fold decreases correspond to approximately **35% and 38% lower incidence**, respectively. The mediator experiments give the lane more discriminating targets than tumor frequency alone. [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC3634644/)

**Why it suits Cells:** there is a tractable physical question—how voltage and sodium gradients affect carrier-mediated uptake—followed by a biological response that can be modeled and tested separately.

### B. Distant tissue effects: Chernet and Levin, 2014

**“Transmembrane voltage potential of somatic cells controls oncogene-mediated tumorigenesis at long-range.”**

Changing electrical state in distant host cells altered ITLS formation. The paper also investigated HDAC1 and bacterial contributions. Its proposed redistribution of bacteria and butyrate is a **mechanistic hypothesis**, not a fully measured spatial transport chain. [Oncotarget](https://www.oncotarget.com/article/1935/text/)

**Why it matters:** this is where a spatial simulator can ask which physical communication routes could support the observations, and which missing measurements distinguish competing explanations.

### C. Gap-junction organization: Chernet, Fields and Levin, 2015

**“Long-range gap junctional signaling controls oncogene-mediated tumorigenesis in Xenopus laevis embryos.”**

This provides an especially strong challenge for the model:

| Published comparison | ITLS incidence |
|---|---:|
| KRAS control | 35% |
| KRAS and H7 separated along the dorsoventral axis | 32.4% |
| KRAS and H7 separated along the left–right axis | 20.5% |

The effect depends on spatial arrangement. The proposed oscillatory explanation remains a model, rather than directly demonstrated embryo-wide voltage dynamics. [frontiersin.org](https://www.frontiersin.org/journals/physiology/articles/10.3389/fphys.2014.00519/full)

**Design consequence:** Cells must not contain a universal rule that stronger gap-junction coupling produces healthier tissue.

### D. Treatment after a lesion exists: Chernet and colleagues, 2016

**“Use of genetically encoded, light-gated ion translocators to control tumorigenesis.”**

The study distinguishes early prevention from delayed treatment after ITLS appearance. Arch and ChR2-D156A reduced formation by about 31–32% in the prevention experiments; delayed activation was assessed separately for normalization. ChR2’s reported voltage effect depends on this preparation’s ion conditions. [Oncotarget](https://www.oncotarget.com/article/8036/text/)

**Why it matters:** this is the eventual visualization milestone—but it requires a longitudinal lesion model. Lowering an endpoint probability after a simulated light pulse would not reproduce physical regression.

### E. Instructor cells and melanocytes: 2008–2017

Morokuma’s 2008 work and Blackiston’s 2011 paper connect ion-channel perturbations with abnormal pigment-cell behavior. The 2011 study develops the instructor-cell/serotonin branch. [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC2575467/)

Lobikin and colleagues’ 2015 **Science Signaling** paper adds serotonergic, cAMP/CREB, and pituitary-linked mechanisms and an inferred stochastic network. That is the important bridge to the later computational work. [pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/26443706/)

Lobo and colleagues’ 2017 paper then used an inferred model to predict a partial-conversion phenotype. The phenotype appeared experimentally, but its frequency differed substantially from prediction: **75% partial in the model versus 22% partial experimentally**, with many animals fully converting instead. This is a useful later benchmark for improving quantitative prediction. [nature.com](https://www.nature.com/articles/srep41339.pdf)

### An essential observation control

Hutchison and colleagues’ 2024 reassessment includes illustrative imaging showing why pigmentation and apparent arborization require careful interpretation: **pigment granules can redistribute within an existing cell**. It is a critical review with new illustrations, not a comprehensive independent refutation of the earlier experiments. [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC10841629)

For Cells, that means four distinct outputs: **cell number, membrane shape, pigment distribution, and cell location/invasion**.

---

## 3. Proposed lane: Xenopus bioelectric cancer

I would use **XC** as a provisional label, with this central question:

> **Can a physically constrained model of ion transport and cell signaling explain several published Xenopus intervention effects with shared parameters, including interventions withheld from calibration?**

The meaningful result is the agreement across interventions. A model that separately fits each experimental bar has learned much less.

### Three levels of result

The lane should explicitly distinguish what it has achieved:

| Level | What the model produces | Appropriate claim |
|---|---|---|
| **Physical reconstruction** | Voltage, ion gradients, transporter current, mediator uptake | Reproduces specified electrical/transport observations |
| **Biological response prediction** | Calibrated response states and ITLS observation likelihood | Predicts specified incidence measurements under declared assumptions |
| **Tissue phenotype simulation** | Proliferation, survival, geometry, organization, and lesion history | Reproduces specified formation or regression behavior |

The first level can begin with relatively small additions. The third requires substantially more biological and numerical qualification.

### Core model

Start with a small tissue containing:

- An oncogene-bearing region.
- Surrounding host cells.
- Explicit extracellular compartments.
- Ion channels, pumps, and the selected carrier.
- A minimal downstream biological response.
- Stable identities and intervention masks.

For the first version, represent each oncogene’s electrical effect through an **empirical change in a declared physical input**, such as channel availability, calibrated to oncogene-only electrical observations. Keep that change fixed across rescue arms. This does not yet simulate the complete molecular signaling of KRAS or Xrel3.

That boundary is important: otherwise an implementation could simply assign the desired depolarized voltage and describe the whole chain as emergent.

---

## 4. The experiments, in build order

### XC0 — Establish the physical preparation

**Question:** Do the modeled cells respond correctly to the interventions before any cancer outcome is introduced?

Begin with one-cell and two-cell preparations, then a small mosaic tissue.

Verify:

- Chloride and potassium equilibrium potentials and current direction.
- Voltage relaxation and membrane capacitance.
- The effect of changing channel availability.
- Sodium-coupled mediator uptake, including saturation, stall, and reversal.
- Material, charge, and energy accounting.
- The distinction between bath and local extracellular compartments.

**Success:** the intervention’s electrical effect emerges from the declared physical conditions and agrees with independent references.

A mismatch is useful. For example, if the assumed ion concentrations cannot produce the reported voltage response, the lane should identify that inconsistency before fitting tumor outcomes.

### XC1 — Local suppression and mechanism disruption

**Question:** Can one transport/response model explain alternative actuators and pathway perturbations?

Use the 2013 study as the first experimental family, keeping its Xrel3 and KRAS assay groups distinct.

A practical calibration/evaluation arrangement is:

| Comparison | Role |
|---|---|
| Unperturbed and oncogene-only conditions | Baseline physiology and susceptibility |
| One hyperpolarizing actuator | Limited calibration where needed |
| A different actuator using a different ion | Withheld intervention |
| Disruption of the proposed transporter | Withheld mechanistic test |
| Added mediator or direct downstream inhibition | Withheld downstream test |
| Transporter disruption plus downstream bypass | New prediction unless the exact combination is verified as published |

For the **first matched three-arm replay**, use:

1. **KRAS alone.**
2. **KRAS + Kir4.1.**
3. **KRAS + Kir4.1 + dominant-negative SLC5A8.**

The evidence ledger should verify the exact assay conditions before these become registered comparisons. Do not combine Xrel3 rescue data and KRAS transporter-disruption data into one apparent matched experiment.

The most informative measurements are the intermediate ones:

- Did voltage change?
- Did sodium and butyrate flux change?
- Did intracellular exposure change?
- Did the downstream response change?
- Did the fixed observation model predict the incidence effect?

**Success:** the complete mechanism predicts the withheld comparisons better than an oncogene-only or direct-voltage statistical baseline, while also matching the physical intermediates.

### XC2 — Remote host influence

**Question:** Can a change in a distant region affect the oncogene-bearing region through an explicitly represented route?

Add separate host and tumor regions connected through declared tissue and extracellular geometry.

Compare candidate mechanisms rather than assuming the complete distant pathway is already known. A candidate might involve metabolite redistribution, source/clearance changes, or junction-mediated communication.

The decisive new tests would include:

- Moving the intervention region.
- Changing distance while controlling topology.
- Cutting a connecting tissue bridge.
- Removing a candidate extracellular route.
- Preserving expression patterns while changing connectivity.

These are proposed model challenges; they should not all be labeled reproductions of published experiments.

**Success:** the effect travels through a specified causal path and changes appropriately when that path is interrupted.

If multiple mechanisms remain compatible with the available data, retain that uncertainty. An attractive spatial replay does not select the correct mechanism.

### XC3 — Gap junctions and anatomical organization

**Question:** Can the model explain why intervention location and anatomical axis matter?

Test local, contralateral, and broad junction perturbations, then evaluate the left–right versus dorsoventral comparison after freezing the model.

There is a basic symmetry constraint here: **an isotropic sheet cannot distinguish left–right from dorsoventral merely because its axes have different names.** The difference must come from independently justified anatomy, connectivity, or developmental physiology.

Likewise, distinguish:

- Electrical coupling.
- Molecular permeability.
- Connexin expression.
- Junction formation and compatibility.

**Success:** the spatial effects emerge from shared rules. An axis-specific coefficient fitted to the desired result would defeat the purpose of the test.

### XC4 — Delayed optogenetic treatment

**Question:** Can the model distinguish prevention, slowed growth, loss of abnormal cells, and restored tissue organization?

This requires two separate cohorts:

- An early-intervention cohort.
- A cohort enrolled only after a lesion already meets a predefined criterion.

For delayed treatment, branch matched lesion states into light and dark conditions. Preserve the spontaneous-regression behavior of the control population.

Before claiming a physical regression result, the engine needs:

- State-dependent proliferation and survival.
- Material supply for growth.
- Persistent cell lineage.
- Tissue organization and suitable geometry dynamics.
- Qualified coupling across the required timescales.

Optical electrophysiology can be tested earlier. A faithful Arch implementation also needs **new optical-energy accounting**, rather than treating light as hidden ATP or assigning a voltage directly.

**Success:** the model represents the lesion before and after intervention and identifies what changed. The disappearance of a rendered mass cannot by itself establish normalization of surviving cells.

### XC5 — Instructor cells and melanocytes

**Question:** Can the model explain the separate pigment-cell observations and their coordination across tissue?

This branch introduces instructor cells, extracellular serotonin, relevant response cells, and melanocytes. Later targets may require pituitary/melanotroph signaling.

Keep the four observable categories separate:

| Observable | What must be represented |
|---|---|
| More pigment cells | Proliferation or altered population allocation |
| Different cell shape | Membrane geometry |
| Darker appearance | Pigment-granule distribution |
| Abnormal tissue location | Cell movement and tissue boundaries |

The 2017 partial-conversion experiment is a useful eventual challenge: predict **normal, partial, and full conversion frequencies**, not merely the existence of an intermediate state.

---

## 5. What makes this a physics-based replication

### Channel effects must follow the gradients

The same channel can have different consequences under different ionic conditions.

Each intervention should modify a physical property—conductance, permeability, carrier abundance, illumination, or an external boundary—and the engine should calculate the resulting voltage.

This is particularly important in Xenopus because **the external bath is not automatically the fluid between embryo cells**. Primary measurements show that ionic concentrations vary with compartment and developmental stage. Using bath concentrations on every internal membrane could change the predicted direction of a channel’s effect. [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC1193846/?page=3)

The species selector therefore needs a preparation identity: cell type, developmental stage, temperature, compartment, and measurement provenance.

### Butyrate uptake needs a coupled-carrier law

For a carrier moving one butyrate anion inward with \(n\) sodium ions, a thermodynamic consistency relation is:

\[
\Delta G_{\mathrm{in}}
=
nRT\ln\frac{a_{\mathrm{Na,in}}}{a_{\mathrm{Na,out}}}
+
RT\ln\frac{a_{\mathrm{B,in}}}{a_{\mathrm{B,out}}}
+
(n-1)FV_m
\]

Here \(V_m\) is inside minus outside potential, and \(a\) denotes activity.

This constrains the driving force, equilibrium, and net charge moved. Kinetics determine the speed.

Coady and colleagues’ 2007 study revisited earlier inconsistent stoichiometric estimates and supported **2:1 coupling** using lactate and propionate measurements. That is a defensible reference assumption, with its transfer to endogenous Xenopus/butyrate physiology stated explicitly. Carrier leak and neutral-acid permeation should remain separate mechanisms where relevant. [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC1965447/)

The implementation should update sodium, substrate, current, and energy from the **same cycle count**. It should not separately calculate an attractive uptake curve and then ignore its electrical consequences.

### SERT requires its own treatment

For the melanocyte branch, avoid implementing “depolarized means serotonin export” as a universal transport law.

Independent SERT work shows that transport/exchange behavior involves intracellular ions and kinetic states, with voltage dependence that is more complicated than a passive serotonin pore. The simple voltage-dependent reversal hypothesis can be compared with a mechanistic carrier model, but the two should be identified separately. [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC5207061/)

### The downstream biological response must be constrained

Voltage and transport do not uniquely determine tumor incidence.

An initial observation model could take the form:

\[
P(\mathrm{ITLS}_e)
=
\operatorname{logistic}
\left(
\alpha_{\mathrm{oncogene}}
+
b_{\mathrm{clutch}}
+
\beta A_e
\right)
\]

where \(A_e\) is a preregistered summary of simulated mediator or HDAC exposure in the oncogene-bearing region.

The important restrictions are:

- The observer receives no intervention name or rescue flag.
- It uses shared parameters across the relevant intervention arms.
- Physical transport parameters come from independent evidence.
- It is labeled as an incidence observation model.

If the data cannot independently constrain the response layer, **the first result should remain a transport reconstruction with conditional phenotype projections**. That is a clear scientific outcome and a useful guide to the next measurement.

---

## 6. Validation that prevents fitting the answer into the model

I would make the following rules part of the lane from its first registered run.

### Keep calibration and evaluation separate

Calibrate physical laws on independent channel/carrier data. Use a small, named set of biological arms for baseline and response calibration. Freeze the model before evaluating alternative actuators, mediator disruption, and later spatial or timing tests.

These are historical experiments already known to the designers. Call them **held out from fitting**, rather than implying that they are new prospective biological experiments.

### Use the correct replicate unit

For ITLS incidence, the unit is the embryo.

Cells, frames, and repeated simulations of one parameter draw are not independent animals. Keep clutch/cohort structure when the source data provide it. If the papers expose only aggregate bars, do not claim leave-clutch-out validation.

Simulated ensembles measure the variability specified by the model. Increasing their size reduces Monte Carlo error, not uncertainty about the biology.

### Score the mechanism in parts

Report separate results for:

1. Electrical behavior.
2. Transport and mediator exposure.
3. Biological response.
4. Incidence or lesion phenotype.

Otherwise, a flexible final observer can hide a physically wrong transport model.

### Preserve informative failures

A result should fail or remain unresolved when:

- Justified ionic conditions cannot reproduce the electrical response.
- Voltage matches but uptake does not.
- The model misses a mediator-disruption result.
- A remote effect requires a direct global shortcut.
- Anatomical selectivity requires fitting the withheld answer.
- Apparent regression is only relabeling or unmodeled cell disappearance.

Each of these outcomes identifies a specific missing mechanism or measurement.

---

## 7. How I would present it in the Xenopus visualization

The first scientific view should be **three synchronized replays of the matched KRAS arms**, with a shared color scale and clock.

Each panel should offer:

| Layer | Purpose |
|---|---|
| Membrane voltage | Show the actual electrical response |
| Intracellular and extracellular butyrate | Show distribution and accumulation |
| Carrier flux and current | Connect electrical state to molecular movement |
| Downstream response | Show the calibrated biochemical consequence |
| Oncogene-bearing region/lineage | Show whether the perturbation persists |
| Experimental comparison | Display the target, model result, and uncertainty |

At the organism scale, the embryo or tadpole provides anatomical orientation and intervention locations. At the tissue scale, the viewer exposes the simulated domain.

Every layer should state whether it is **simulated, modeled in aggregate, prescribed, or illustrative**. Fixed tissue geometry is perfectly useful, provided it is described as prescribed rather than represented as emergent growth.

Cells already has the right output direction: use the shared [`cells.run_view@1` writer](https://github.com/Eidosoma/Cells/blob/b546c99d615a1fa8ff611e49ff272337f334d5f2/src/cells/records/run_view.py) and existing adapter. The viewer should display recorded quantities and the experiment’s verdict, preserving the distinctions in the [species contract](https://github.com/Eidosoma/Cells/blob/b546c99d615a1fa8ff611e49ff272337f334d5f2/visualizer/schema/SPECIES.md).

For the later optical experiment, mark **the established lesion, treatment time, and continuing lineage**. For the melanocyte branch, pigment distribution should have its own layer so that a darker animal cannot silently stand for more cells.

---

## 8. The first implementation bundle I would give the Cells agents

I would start with this bounded assignment:

> **Implement XC0 and the local transport component of XC1 using `resolved_pump_tissue@3` and `resolved_pump_composite@1`. Qualify a sodium/monocarboxylate carrier on the existing cycle host, build a small mosaic tissue, and produce a matched KRAS three-arm replay. Separate physical observations from fitted biological responses. Evaluate an alternative actuator and mediator disruption after freezing the relevant parameters.**

The concrete deliverables are:

1. **A compact evidence ledger** with source locations, assay conditions, units, uncertainty, and calibration/evaluation roles.
2. **One-cell and two-cell physical preparations** with independent checks.
3. **The reusable carrier law**, with charge and energy accounting.
4. **A small tissue comparison** including a mechanism-disruption control.
5. **A qualified response model where the evidence supports one**, with unresolved quantities left explicit.
6. **One results report and replay**, showing matches, misses, and the limits of the claim.

Keep the first preparations CPU-sized and profile the tissue case before allocating a large ensemble. The current factored solver permits up to 2,048 combined cell and extracellular nodes, but biological duration is a separate challenge: a long-time reduction must be qualified for the new coupled model and its interventions. Existing GPU throughput does not automatically solve that problem. The repository’s [current plan](https://github.com/Eidosoma/Cells/blob/b546c99d615a1fa8ff611e49ff272337f334d5f2/docs/CURRENT_PLAN.md) already recognizes that distinction.

**The strongest first success would be one model that predicts how two different electrical interventions alter transport—and correctly predicts when disrupting the transporter removes the biological effect.** That would give the new Xenopus visualization a substantive experimental foundation and create a disciplined route toward the more ambitious long-range and tumor-normalization papers.
