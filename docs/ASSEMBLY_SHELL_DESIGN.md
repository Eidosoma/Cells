# A prescribed shell with a lumen, an exchange conductance and exposed sites (FR-21): design note

**Status: proposed, 20 November 2026, by the operators owner; decided the same evening (D244), by the lead with the advisor under the user's delegation. D244 records the choices and any departures from this note's recommendations.** Desk work
only (D142): options, a recommendation, what stays bitwise, files, tests and a price, before any
code. It describes a general feature (D144) of `cells.assembly_lineages@2`. Nothing is built.

**The request** ([FEATURE_REQUESTS.md](FEATURE_REQUESTS.md) FR-21; D237):
- **What:** let a prescribed protein shell own a lumen and an exchange conductance, independent of
  the membrane's inventory and of its binding-site count.
- **Why:** to attribute a result to area or to permeability. Today every cross-phase reaction routes
  through the membrane phase. The existing two-state gate is enough to test kinetics, but not to
  separate those two causes.

**Why now.** FR-20's pulse and washout, approved in D240, lists tracer captured on an exposed-site
control as a non-claim until FR-21 exists. D240 says: "An exposed site that binds in one step is
FR-21's ground" ([ASSEMBLY_WASHOUT_DESIGN.md](ASSEMBLY_WASHOUT_DESIGN.md) §1, :46–52).

**Engine models it would run:** `cells.assembly_lineages@2`, in single-lineage and population mode,
with:
- `cells.shared_pool@1`;
- `cells.stochastic_mass_action@1` with `count_on_m`, for one-step site binding (§4.1);
- a new geometry, `cells.prescribed_shell@1`, the second implementation of
  `cells.assembly_geometry@1`;
- a new entry law for a shell, `cells.shell_permeation@1`, beside an unchanged
  `cells.membrane_permeation@1`;
- where a shell is gated, a new gate factor over the gate's own forms (§4.3);
- for FR-20's control, `cells.pool_replacement@1`.

**Code read at 5011ed3d.** The version-2 files were unchanged then. The origin-of-life builder is
changing them now for FR-20, so line numbers will drift. Paths are under
`src/cells/models/assembly_lineages_v2/` unless they say otherwise. **S** marks our own reading or
derivation.

## 0. Summary

| | |
| --- | --- |
| **The gap** | A world with a geometry admits only two cross-phase steps, a join and an entry. The entry's encounter is the bilayer's area, computed from the membrane's counts. Each membrane species takes at least one quantum of area, so binding sites add area. Binding from the pool in one step is refused |
| **Recommended** | Three pieces, in two steps. **First,** one-step site binding: rule 3 admits the existing mass-action law with `count_on_m` for the binding shape, its encounter being the site count. This needs no new law. **Second,** the prescribed shell: a geometry whose area and lumen are declared, with its own entry law, so its conductance follows neither the wall's counts nor the site count. Where the shell is gated, a gate factor that counts only the gate's own forms |
| **What FR-20 gains** | Its exposed-site control becomes expressible: a pulse loads the sites, and a washout keeps the bound tracer. A closed or open lumen tells retention on sites from capture inside |
| **Bitwise** | Every existing version-2 world, the invariance gate and OL5's references. No registered law's text changes, and no version-2 protocol is registered or judged |
| **Price** | Development: 5–7.5 agent-days for all three pieces, or 0.75–1.25 for site binding alone. If the lead's answer on rule 3 needs a named law (§4.1), these become 5.5–8.25 and 1.25–2. Gates are excluded |
| **Builder** | The origin-of-life builder owns the version-2 files and is on FR-20 now, so this follows FR-20, unless the lead grants a recorded exception |

## 1. What exists today, and what refuses

**In a world with a geometry:**
- **Rule 3 refuses every other interface.**
  - **The ruling:** in a world that declares a geometry, a cross-phase step takes a geometric
    encounter law, phase exchange for a join and permeation for an entry. "A join from the lumen,
    an interfacial reaction and a pool-to-lumen reaction are refused until a geometric encounter is
    declared for them" (ORIGIN_OF_LIFE_ENGINE_DESIGN.md §0.2c rule 3, :221–227).
  - **The code:** `spec.py:342–349`, "world: step {id} crosses phases at the membrane; in a world
    with a geometry a cross-phase step takes a geometric encounter law (phase exchange for a join,
    permeation for an entry), and other interfaces are refused until one is declared (§0.2c rule
    3)".
  - **The two laws' shapes are fixed:** a join or an entry, one molecule of one species
    (`_geometric_shape`, `spec.py:370–387`).
- **The entry's conductance is the bilayer's area, from the counts.**
  - **The law:** `permeation.py:5–13` gives a⁺ = P_s · A(m) · ρ0 · θ⁺, with A(m) = q·W(m)/2 and W
    the membrane's footprint in area quanta.
  - **Every permeation uses the area code** (`model.py:194–195`).
  - **The kernel** computes ln(E·ρ0) from W(m) (`kernel.py:327–337`).
- **Sites add area.** Each membrane species declares at least one quantum
  (`geometry.py:134–135`). So a site, or a bound complex, adds to W and therefore to the area.
- **The gate reads the membrane's composition.** Its factor is g = 1 + z(m)/N(m), the open form's
  share of all membrane molecules (`transition_state.py:130–140`).
- **The lumen** is either osmotic or declared.
  - **Osmotic:** its volume comes from the counts, capped by the sphere of area A (`lumen.py:114–121`).
  - **Declared:** one constant `volume_L` per world (`conventions.py:43`; `world.py:296–304`).
  - **c_ext exists only for an osmotic lumen.** It comes from the osmotic term (`lumen.py:55–60`).
    The transfer's refusal of fresh solutes above c_ext, which FR-20's replacement keeps, returns
    early for any other lumen (`transfer.py:60–61`).
  - **A population world with a declared lumen fails** when its rows are assembled.
    `population.py:716–719` calls the osmotic routines unconditionally, and `lumen.py:86–93` needs
    c_ext. The Lean project recorded this as an engine finding (`lean/PROGRESS.md`, its shared-pool
    declared-volume entry).
- **A population needs a geometry,** for its floor: "its floor keeps every vesicle from emptying"
  (`population.py:59–63`).
- **The geometry interface is parse-only** (`interfaces.py:99–120`).
  - The bilayer's quantities are module functions, imported directly in `model.py`, `spec.py`,
    `lumen.py`, `runner.py`, `population.py`, `records.py` and `division.py`.
  - The structure keeps the geometry's ID (`kernel.py:130`, `model.py:48`). The kernel uses it only
    as a static presence test, which keeps OL1's programs unchanged (`kernel.py:275–295`, :516). It
    selects no geometry kind.
- **The registered laws.** `cells.membrane_permeation@1`'s registered formula reads
  "A(m) = q W(m)/2" (`permeation.py:32–34`).
  - The Lean project's registry lists the law with its source line (`lean/registry.json`, its `law`
    map).
  - Its commit 5011ed3d, by its title, registers direct proofs for all current laws.

**In a world without a geometry** (option S0's ground):
- **One-step binding already runs.** Rule 3's last sentence keeps `count_on_m` on every
  membrane-locus step there. The mass-action law's membrane factor cancels to the free-site count
  for a step that turns one site into one complex, so a⁺ = k_f·θ⁺·n_S
  (`mass_action.py`, its docstring at :1–29, and `membrane_factor`, :76).
- **But the entry's extent is the membrane's count.** A pool-to-lumen step there has the extent
  N(m) − c + 1 (`mass_action.py:17`), so its conductance follows the membrane's count, sites
  included.
- **Permeation and phase exchange are refused** without a geometry (`spec.py:335–340`), and so is a
  population (above).

**The capsid models are no base for this** (docs/CAPSID_ASSEMBLY.md). They are a separate family
with a prescribed 20-site cage, and they have no free energy, no lumen and no permeation.

## 2. The test every option must pass

The request's reason is to separate area from permeability. So an option passes only if the area,
the permeability (and so the conductance), the lumen volume and the site count can each be
declared apart from the others and from any membrane inventory.

| Quantity | A bilayer vesicle today | A prescribed shell (§4) |
| --- | --- | --- |
| Area A | q·W(m)/2, from every membrane species' counts | Declared |
| Lumen volume | Osmotic, from the counts and A; or one declared constant | Declared |
| Exchange conductance G_s = P_s·A | P_s·A(W), following the inventory | P_s·A_sh, both declared, by the shell's own entry law |
| Binding-site count | A membrane species' count, which adds area | A wall species' count, which sets neither the area nor the volume |
| Binding from the pool in one step | Refused (rule 3) | Admitted for the binding shape (§4.1) |
| A gate on the entry | 1 + z(m)/N(m), diluted by every membrane molecule | Over the gate's own forms (§4.3), so the site count does not dilute it |

## 3. Options

| Option | What | Passes §2? | For | Against |
| --- | --- | --- | --- | --- |
| S0 | No code and no geometry: one-step binding by mass action, and a declared lumen | No. The entry's extent is the membrane's count, sites included | Runs today, single-lineage | No permeation law and no population mode, so FR-20's control is not served |
| S0′ | No code, with the bilayer: a rigid vesicle whose membrane never exchanges, with a declared lumen | No. A follows W, which also carries the sites; there is no one-step binding | Nothing to build | The declared lumen fails in population worlds (§1) |
| S1 | One-step site binding: rule 3 admits the mass-action law with `count_on_m` for the binding shape, on any geometry | In part. Sites bind in one step, but on a bilayer they still add area | The smallest piece, with no new law. It gives FR-20's control on vesicles | No shell: the lumen and the conductance still follow the inventory. Its encounter is a count, not the geometric encounter rule 3 names, so the lead may refuse it |
| S1′ | The same binding through a named law, `cells.site_binding@1`, the encounter law rule 3 asks for. Its encounter is the site count, with a diffusion-limited form as an option | As S1 | It answers rule 3 with a named encounter law | A new law, its kernel code and its registration: 1–1.5, against S1's 0.5–0.75 |
| S2 | The prescribed shell, with its own entry law | In part: area, lumen and conductance, but no sites | — | No exposed site, so FR-20's control is not served |
| G | A gate factor over the gate's own forms | Needed only for a gated shell with sites | It is also the right open fraction for a pore on a bilayer | A new factor law |
| **S3** | **S1 and S2, with G where the shell is gated** | **Yes** | The request whole, and FR-20's control on shells and on vesicles | The largest |
| S4 | Reuse the capsid family | No | Its prescribed cage | No free energy, lumen or permeation, and another family |

**Recommended: S3, in two steps.** S1 first, since it serves FR-20's control on its own; S1′ in its
place if the lead requires a named encounter law (§10, question 6). Then S2, with G if the shell is
gated.

## 4. The design (S3)

### 4.1 One-step site binding: rule 3's door

- **The step.** One molecule of a pool place binds a site place of the wall (the membrane phase),
  forming a complex place in the same phase: X(pool) + S → C. It is declared in this direction only,
  in rule 2's form. Its reverse comes from F, as every reverse in the family does.
- **The law is the existing `cells.stochastic_mass_action@1`, with `count_on_m`.**
  - For this shape its membrane factor cancels to the free-site count (`mass_action.py`, its
    docstring). So a⁺ = k_f·θ⁺·n_S, with θ⁺ the pool's activity.
  - The reverse is the same law applied to the products: a⁻ = k_f·exp(Σνμ°)·n_C, with the complex's
    potential from the registry (K_d).
  - k_f is in the activity form (`forward_rate_per_s`), so k_f = k_on·c0. It carries its provenance
    (§0.2e item 3).
- **The encounter is the site count, not an area.** Binding is reaction-limited, per site (**S**). A
  diffusion-limited encounter is an option, at +0.5 (§9).
- **Rule 3 is amended,** which is the lead's ruling to make.
  - **Admitted:** an interfacial step of exactly this shape, one pool molecule and one declared site
    forming one complex in the wall, under `count_on_m`.
  - **Still refused:** every other interfacial step, a join from the lumen and a pool-to-lumen
    reaction.
  - Sites and complexes are declared as such, so the parse checks the shape.
- **No new law and no kernel change (S, read, not run).**
  - **The law's direction never reads the geometric encounter.** `log_direction`
    (`mass_action.py:102–123`) uses only the counts and its own membrane factor.
  - **The kernel sets every step's code-0 encounter to 0.** Its floor and last-molecule tests then
    apply to this step as to any membrane-locus step (`kernel.py:270–300`).
  - **A population counts any step that touches a slot's place as a slot channel,** with nothing
    keyed on the law (`population.py:175–184`).
  - So the change is the parse's admission (`spec.py:342–349`).
  - **The risk: no such step has ever run in either setting.** Rule 3 refuses a cross-phase
    mass-action step in a world with a geometry, and a population needs a geometry. The geometry
    test covers only the refusal (`tests/unit/test_assembly_lineages_v2_geometry.py:335–340`). S1's
    price allows for this at its upper end (§9).
- **The alternative, S1′.** If the lead holds that rule 3 needs a named encounter law, binding goes
  through `cells.site_binding@1`, with the same rates and its own kernel code, at 1–1.5 (§9).
- **Langmuir from F (S).**
  - The wall's condensed measure is multinomial. With the wall's other species and the site total
    conserved, the free and bound sites' configurational term is ln C(R + B, B), up to a constant.
  - So at a held pool the stationary distribution of B on N sites is binomial with
    p = c/(c + K_d): Langmuir in the mean. A test checks it from the kernel's rates (§7).
- **On any geometry.**
  - **On a bilayer,** sites are membrane species with their area quanta: receptors take area, which
    is physical. So on vesicles the site count is not independent of the inventory.
  - **On a shell,** sites set nothing (§4.2).
  - **Sites with no area on a bilayer** would relax §0.2e item 5. That is an option, at +0.5 (§9).
- **Labels (rule 17):** a bound tracer keeps its label on the complex place.
- **Division (rules 9–10):** on a bilayer, sites split with the membrane's molecules, since C3x
  already covers every membrane species. On a shell, division is refused (§4.2).

### 4.2 `cells.prescribed_shell@1`, and its entry law

- **The declaration.** `geometry: {law: "cells.prescribed_shell@1", area_m2: {value, provenance}}`.
  The lumen uses the existing `lumen_volume: declared`, with `phases.lumen.volume_L`.
- **The wall is the membrane phase.**
  - Its species (subunits, and free and bound sites) carry no area quanta, so no
    `area_per_leaflet` is declared.
  - Their counts set neither the area nor the lumen.
- **Its own entry law, `cells.shell_permeation@1`.**
  - **The rate:** a⁺ = P_s·A_sh·ρ0·θ⁺, with A_sh the shell's declared area and P_s in m/s, the
    bilayer's unit. The reverse is the same law applied to the products, as permeation's is.
  - **Its encounter is a constant of the world:** a new kernel code, dispatched statically by the
    geometry kind.
  - So the conductance G_s = P_s·A_sh is independent of the wall's counts, of the site count and of
    the lumen. The run reports G_s per species.
  - **Why a law of its own (D147).** `cells.membrane_permeation@1`'s registered formula reads
    A(m) = q·W(m)/2, and the Lean project's registry lists the law (§1). A new law leaves both as
    they are.
  - **The alternative** generalises that law's formula to "A from the geometry". It keeps one law
    for vesicles and shells, but it changes a registered law's text, and the Lean project would then
    register its proof again (§10).
- **Joins are refused in version 1:** a prescribed wall takes up no amphiphiles.
  - But "independent of the membrane's inventory" may mean an inventory that still varies. A shell
    world could keep an exchanging membrane, with the join's encounter taken from the declared area.
  - That is the user's question (§10). Its price is +1–1.5.
- **What a shell refuses,** each at the parse with its reason:
  - phase exchange (a join), unless the user's answer keeps an exchanging membrane;
  - `lumen_volume: osmotic`: the wall does not swell;
  - `vesicle_floor`, a closure cost and `sigma_max`: no floor, tension or lysis applies;
  - division and shear events: in version 1 a prescribed shell neither divides nor breaks.
- **The rules, one by one:**

  | Rule | For a shell |
  | --- | --- |
  | 1, conditional keys | The shell is a value of the existing `geometry` key. When it is absent nothing is written, so OL1's ids and fingerprints do not move. `exchange_encounter` is required with a geometry: absent in a shell world without joins, and required if the user keeps them (§10) |
  | 2, directions | Each entry stays an entry. Site binding is declared in one direction only (§4.1) |
  | 3, interfaces | Amended for the binding shape (§4.1) |
  | 4–5, area quanta and the floor | No quanta and no floor. No step changes the wall's area. A population needs a geometry so that no vesicle empties (`population.py:59–63`). A prescribed wall cannot empty, since nothing leaves it, so that check is widened to admit the shell (**S**). A geometry also requires `last_molecule: kept` (`spec.py:352–356`); a shell keeps the requirement, which is met trivially, since no step removes a wall molecule |
  | 6–8, the lumen, c_ext and lysis | The lumen is declared, so there is no c_ext. Rule 6's check and the transfer's refusal do not apply (`lumen.py:55–60`; `transfer.py:60–61`), and no c_ext drift is reported. There is no lysis |
  | 9–10, division | Refused |
  | 14, streams | No new draws |
  | §0.2e item 3, provenance | `area_m2`, P_s and k_f carry their provenance |

- **Dispatch.** The kernel already tests the structure's geometry ID statically, for presence
  (§1). Extending that test to the kind, at the bilayer's direct-import sites, lets bilayer worlds
  trace today's programs, as the presence test keeps OL1's (**S**).
- **Population mode.**
  - Slots hold the wall's places and the lumen's.
  - In version 1, the shell's area and volume are world constants: one shell type per world.
  - The declared-lumen row failure (§1) is fixed first.
- **FR-22's checkpoints carry over,** since the state stays integer counts.

### 4.3 A gate on a shell

- **The problem.** The transition-state factor's denominator is every wall molecule,
  g = 1 + z(m)/N(m) (`transition_state.py:130–140`). With sites in the wall, two shells that differ
  only in their site count get different gated entry rates. So a gate breaks the independence the
  request asks for.
- **F does not couple them (S).** With the gate's forms and the sites each conserved, the wall's
  multinomial term splits into one binomial for each, up to a constant. Only the factor's
  denominator couples them.
- **Options:**

  | Option | What | For | Against |
  | --- | --- | --- | --- |
  | G1 | Sites in a phase of their own, so N(m) excludes them | Sites without area on a bilayer come with it | The binding step leaves `count_on_m`'s membrane locus, so it needs its own encounter and phase rules: +1–1.5 |
  | **G2** | A gate factor whose denominator is the gate's own forms, g = 1 + z(m)/(n_open + n_closed)(m). It is a new factor law beside the transition-state factor, applied to both directions as that one is, so detailed balance is kept (**S**) | It is also the right open fraction for a pore on a bilayer | A new factor law: +0.5–1 |
  | G3 | A declared limit: the independence holds for an ungated entry only | Nothing to build | The requester uses the gate |

  **Recommended: G2,** built with S2 where the shell is gated.

### 4.4 What it lets FR-20's exposed-site control do

- **Today.** Binding from the pool needs a join into the membrane, then a membrane-locus step: two
  steps, with the sites adding area. So "tracer captured on an exposed-site control" is FR-20's
  non-claim (ASSEMBLY_WASHOUT_DESIGN.md:46–52; D240).
- **With S1:**
  - an exposed site binds tracer in one step;
  - a pulse, a pool replacement holding tracer, loads the sites;
  - a washout, tracer-free, keeps every slot's places, and so keeps the bound tracer
    (ASSEMBLY_WASHOUT_DESIGN.md §1, :26–27);
  - the tracer then unbinds into the finite wash bath, from which it can bind again (:35–37).
- **With S2 as well,** and G where gated, the control is a shell whose lumen is closed (P_s = 0) or
  open. Retention on sites and capture in a lumen are then told apart, with the site count, the area
  and the conductance each declared alone.
- **FR-20's operator needs no change.**
  - "Nothing in it is specific to a bilayer" (ASSEMBLY_WASHOUT_DESIGN.md:51–52).
  - Its file, `replacement.py`, is not on disk yet. Its note keeps the transfer's c_ext refusal as
    it is (its Q4). That refusal is skipped for a declared lumen (`transfer.py:60–61`), so this holds
    if the builder keeps the transfer's guard.

## 5. What stays bitwise

- **Every existing version-2 world**, in values, programs and structure.
  - No new key is written unless declared.
  - The new code paths are dispatched statically, on the geometry's kind and on the step's law.
  - Rule 3's admission adds no kernel path, by the code read in §4.1 (**S**); S1's tests exercise it
    first.
- **No registered law's text changes.** The mass-action law is reused as it is, and permeation and
  the transition-state factor are left alone. The shell's entry law and the gate factor are new
  IDs; the Lean project's own generator lists them as new, which is that project's work.
- **The invariance gate** (`scripts/assembly_lineages_invariance.sh`) stays unchanged: @1's freeze
  test, its part-1 references and probe sets, G2's ten rows and OL1's probe set. No OL2 world is in
  it.
- **OL5's code-blind references** (`validation/ool/references`), whose worlds do not change.
- **No version-2 protocol is registered or judged.** PROGRESS.md's OL1 entry says "Nothing is
  judged under a registered protocol", and OL2 and OL3 landed as development (merge d1697656). This
  is checked again at the landing.
- **FR-20's pool replacement and FR-22's checkpoints:** their worlds are unchanged.

## 6. Files and owners

- **The builder.** The origin-of-life builder owns the version-2 files (§0.2c rule 16;
  CORE_SEAMS_DESIGN.md §18) and is changing them now for FR-20. So FR-21 is built after FR-20 lands:
  by that builder, or by another seat under a recorded exception from the lead.
- **New, in the version-2 package:** `prescribed_shell.py`, `shell_permeation.py`, and a module for
  G2's gate factor.
- **Changed:**
  - `__init__.py`: the law IDs;
  - `spec.py`: rule 3's admission for the binding shape, the shell's refusals, and the population's
    geometry check widened to the shell;
  - `model.py` and `kernel.py`: the shell's encounter code, dispatched statically;
  - `world.py`: a wall without area quanta, and the declared sites and complexes;
  - the bilayer's import sites, for the dispatch: `lumen.py`, `runner.py`, `population.py` (with the
    declared-lumen fix), `records.py` and `division.py`;
  - `interfaces.py`, if the geometry interface gains methods.
- **`src/cells/registry/model_table.py`:** the version-2 rows. The builder edits them, and the F
  owner owns the table's structure (CORE_SEAMS_DESIGN.md §18).
- **Docs:**
  - `validation/assembly_lineages_v2/FORMAT_OL2.md` gains a section;
  - `docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md` gains rule 3's amendment and the shell's rows, as a §0.2
    ruling entry.
- **Not edited here:** `lean/registry.json` and `lean/COVERAGE.md`. They follow from the Lean
  project's own generator (`lean/scripts/generate_claims.py`), and that project is another agent's.

## 7. Tests (D224)

**Tier 1, rows only:**
- **`tests/unit/test_assembly_lineages_v2_spec.py`** (2 s):
  - the binding shape is admitted in a world with a geometry;
  - every other interfacial step is still refused, as are a join from the lumen and a
    pool-to-lumen reaction;
  - the shell's refusals, one row each: a join, an osmotic lumen, `area_per_leaflet`, a floor,
    `sigma_max`, division and shear.
- **`tests/unit/test_assembly_lineages_v2_registration.py`** (7.6 s): the new laws and the geometry
  in its exact sets.

**Tier 2, three compiled rows,** each with its seconds and reason stated at the landing:
- **In `test_assembly_lineages_v2_kernel.py`** (43 s today), S1:
  - site binding's forward and reverse propensities, against k_f·θ⁺·n_S and k_f·exp(Σνμ°)·n_C;
  - at a held pool, the stationary binomial, from the rates' ratio (detailed balance);
  - about 15–25 s more.
- **In `test_assembly_lineages_v2_geometry.py`** (28.85 s today; it holds the permeation
  closed-form test), S2:
  - a shell's entry propensity equals P_s·A_sh·ρ0·θ⁺ at two wall compositions and two site counts,
    and it is the same in all four;
  - doubling A_sh while halving P_s leaves it equal to rounding;
  - about 15–25 s more.
- **In the same file,** G: two gated shells that differ only in their site count have equal gated
  entry propensities. About 10–20 s more, if it shares the S2 row's program.
- **Planted errors (D187):**
  - a reverse without the site term: the binomial check fails;
  - a shell whose entry reads W: the equal-conductance check fails;
  - the transition-state factor in G2's place: the equal-gated check fails.

**FR-20's test file** (the builder's, in progress) **takes one row:** a pulse and washout on a
shell population with exposed sites keeps the bound tracer at the replacement and then releases it
into the finite wash bath. About 20–30 s.

## 8. Acceptance, from the request

1. **A prescribed shell owns a lumen and an exchange conductance.** Its lumen volume and its
   G_s = P_s·A_sh are the declared values, whatever the wall's counts and the site count.
2. **Independent of the membrane's inventory and of its binding-site count.** Changing the wall's
   composition or its site count leaves the entry propensity and the lumen volume unchanged, bit for
   bit. With a gated entry this holds through G2's factor (§4.3).
3. **For FR-20:** an exposed site binds tracer in one step, and a washout keeps the bound tracer.

## 9. Price (S)

| Part | Agent-days |
| --- | --- |
| S1: rule 3's admission for the binding shape, the declared sites and complexes, the parse checks. The upper end allows for a path never run before (§4.1) | 0.5–0.75 |
| S2: the geometry dispatch made real at the bilayer's import sites, static by kind | 1–1.5 |
| S2, `cells.prescribed_shell@1`: parse and refusals, the population check, the run's reports | 1–1.5 |
| S2, `cells.shell_permeation@1`: the law, its kernel code, registration | 0.5–0.75 |
| The declared-lumen fix in population rows, unless the builder's repairs carry it | 0.25–0.5 |
| G2: the gate factor over the gate's own forms, for a gated shell | 0.5–1 |
| Tests | 0.75–1 |
| Docs and FORMAT_OL2.md | 0.5 |
| **All, development** | **5–7.5** |
| S1 alone, with its tests and docs | 0.75–1.25 |
| If rule 3 needs a named law: S1′, `cells.site_binding@1` in S1's place | 1–1.5, so all 5.5–8.25 and S1′ alone 1.25–2 |
| Optional: an exchanging membrane under the shell, with joins at the declared area | +1–1.5 |
| Optional: sites with no area on a bilayer | +0.5 |
| Optional: per-slot shells, with heterogeneous sizes in one population | +1–1.5 |
| Optional: a diffusion-limited site encounter (4πD·r per site) | +0.5 |
| Code-blind references in OL5's form, for the shell's exchange and site binding | +1.5–2 |
| A registered protocol | +1–2 |

Calibration: FR-20's operator, at 1.75–2.5 (ASSEMBLY_WASHOUT_DESIGN.md §8). OL2's first milestone
built the bilayer geometry, phase exchange and permeation together (ORIGIN_OF_LIFE_ENGINE_DESIGN.md
§0.2e item 1).

## 10. Questions

**For the user:**
1. S3 in two steps, S1 first, or S1 alone for now?
2. The shell's entry: a law of its own (recommended), or `cells.membrane_permeation@1` generalised,
   which keeps one law but changes a registered law's text? And P_s with a declared area
   (recommended), or a declared G_s per species?
3. Does a shell world keep an exchanging membrane, with the join's encounter from the declared area,
   or is its wall prescribed, as recommended for version 1?
4. One shell type per world in version 1, or per-slot shells?
5. Exposed sites on bilayer vesicles too (recommended)? And should those sites take area?

**For the lead:**
6. Rule 3's amendment for the binding shape (§4.1): is the site count an admissible encounter
   (S1, 0.5–0.75), or does rule 3 need a named encounter law (S1′, 1–1.5)?
7. Who builds, and when: the origin-of-life builder after FR-20, or another seat under a recorded
   exception?
8. Rule 1's `exchange_encounter` in a shell world: absent without joins, and required if question 3
   keeps them?
