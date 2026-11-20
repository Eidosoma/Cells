# A prescribed shell with a lumen, an exchange conductance and exposed sites (FR-21): design note

**Status: proposed, 20 November 2026, by the operators owner, for the lead and the user.** Desk work
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
- a new geometry, `cells.prescribed_shell@1`, the second implementation of
  `cells.assembly_geometry@1`;
- a new step law, `cells.site_binding@1`;
- the existing `cells.membrane_permeation@1`;
- and, for FR-20's control, `cells.pool_replacement@1`.

**Code read at 5011ed3d.** The version-2 files were unchanged then. The origin-of-life builder is
changing them now for FR-20, so line numbers will drift. Paths are under
`src/cells/models/assembly_lineages_v2/` unless they say otherwise. **S** marks our own reading or
derivation.

## 0. Summary

| | |
| --- | --- |
| **The gap** | A world with a geometry admits only two cross-phase steps, a join and an entry. The entry's encounter is the bilayer's area, computed from the membrane's counts. Each membrane species takes at least one quantum of area, so binding sites add area. Binding from the pool in one step is refused |
| **Recommended** | Two pieces, built in two steps. First, `cells.site_binding@1`, the declared encounter that rule 3 asks for: an exposed site binds a pool molecule in one step, on any geometry. Second, `cells.prescribed_shell@1`: the shell's area and lumen are declared, and its wall's counts set neither |
| **What FR-20 gains** | Its exposed-site control becomes expressible: a pulse loads the sites, and a washout keeps the bound tracer. A closed or open lumen tells retention on sites from capture inside |
| **Bitwise** | Every existing version-2 world, the invariance gate and OL5's references. No version-2 protocol is registered or judged |
| **Price** | Development: 4.5–6.5 agent-days for both pieces, or 1.75–2.5 for site binding alone. Gates are excluded |
| **Builder** | The origin-of-life builder owns the version-2 files and is on FR-20 now, so this follows FR-20, unless the lead grants a recorded exception |

## 1. What refuses today, and why

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
  - **A population world with a declared lumen fails** when its rows are assembled.
    `population.py:716–719` calls the osmotic routines unconditionally, and `lumen.py:86–93` needs
    the outside's osmolarity. The Lean project recorded this as an engine finding
    (`lean/PROGRESS.md`, its shared-pool declared-volume entry).
- **The geometry interface is parse-only** (`interfaces.py:99–120`).
  - The bilayer's quantities are module functions, imported directly in `model.py`, `spec.py`,
    `lumen.py`, `runner.py`, `population.py`, `records.py` and `division.py`.
  - The structure keeps the geometry's ID (`kernel.py:130`, `model.py:48`). The kernel uses it only
    as a static presence test, which keeps OL1's programs unchanged (`kernel.py:275–295`, :516). It
    selects no geometry kind.
- **The capsid models are no base for this** (docs/CAPSID_ASSEMBLY.md). They are a separate family
  with a prescribed 20-site cage, and they have no free energy, no lumen and no permeation.

## 2. The test every option must pass

The request's reason is to separate area from permeability. So an option passes only if the area,
the permeability (and so the conductance), the lumen volume and the site count can each be
declared apart from the others and from any membrane inventory.

| Quantity | A bilayer vesicle today | A prescribed shell (§4) |
| --- | --- | --- |
| Area A | q·W(m)/2, from every membrane species' counts | Declared |
| Lumen volume | Osmotic, from the counts and A; or one declared constant | Declared |
| Exchange conductance G_s = P_s·A | P_s·A(W), following the inventory | P_s·A_sh, both declared |
| Binding-site count | A membrane species' count, which adds area | A wall species' count, which sets neither the area nor the volume |
| Binding from the pool in one step | Refused (rule 3) | Admitted, through a declared encounter |

## 3. Options

| Option | What | Passes §2? | For | Against |
| --- | --- | --- | --- | --- |
| S0 | No code: a rigid vesicle, the bilayer geometry with a membrane that never exchanges and a declared lumen | No. A follows W, which also carries the sites; there is no one-step binding | Nothing to build | The declared lumen fails in population worlds (§1) |
| S1 | One-step site binding only, `cells.site_binding@1`, on any geometry | In part. Sites bind in one step, but on a bilayer they still add area | The smallest piece; it gives FR-20's control on vesicles at once | No shell: the lumen and the conductance still follow the inventory |
| S2 | The shell geometry only, `cells.prescribed_shell@1` | In part: area, lumen and conductance, but no sites | — | No exposed site, so FR-20's control is not served |
| **S3** | **S1 and S2** | **Yes** | The request whole, and FR-20's control on shells and on vesicles | The largest |
| S4 | Reuse the capsid family | No | Its prescribed cage | No free energy, lumen or permeation, and another family |

**Recommended: S3, in two steps.** S1 first, since it serves FR-20's control on its own; then S2.

## 4. The design (S3)

### 4.1 `cells.site_binding@1`: the encounter that rule 3 asks for

- **The step.** One molecule of a pool place binds a site place of the wall (the membrane phase),
  forming a complex place in the same phase: X(pool) + S → C. It is declared in this direction only,
  in rule 2's form. Its reverse comes from F, as every reverse in the family does.
- **The forward.** a⁺(n) = k_on · c0 · θ⁺(n) · n_S(m).
  - k_on is per site and per concentration (`association_rate_per_mM_per_s`), with its provenance
    (§0.2e item 3).
  - θ⁺ is the pool's activity, and n_S the free-site count on the pair's common state.
- **The reverse:** k⁻ = k_on·c0·exp(Σνμ°), with the complex's potential from the registry (K_d), so
  detailed balance holds by construction (**S**).
- **Langmuir from F (S).**
  - The wall's condensed measure is multinomial. With the wall's other species and the site total
    conserved, the free and bound sites' configurational term is ln C(R + B, B), up to a constant.
  - So at a held pool the stationary distribution of B on N sites is binomial with
    p = c/(c + K_d): Langmuir in the mean. A test checks it from the kernel's rates (§7).
- **Rule 3.** This law is the declared encounter for the interfacial step. A mass-action
  interfacial step, a join from the lumen and a pool-to-lumen reaction stay refused.
- **On any geometry.**
  - **On a bilayer,** sites are membrane species with their area quanta: receptors take area, which
    is physical. So on vesicles the site count is not independent of the inventory.
  - **On a shell,** sites set nothing (§4.2).
  - **Sites with no area on a bilayer** would relax §0.2e item 5. That is an option, at +0.5 (§9).
- **The kernel.** A new encounter code, whose extent is the free-site count. It is set by the step's
  law, as `model.py:189–195` sets the codes today, so a world without the law traces today's program
  (**S**).
- **Labels (rule 17):** a bound tracer keeps its label on the complex place.
- **Division (rules 9–10):** on a bilayer, sites split with the membrane's molecules, since C3x
  already covers every membrane species. On a shell, division is refused (§4.2).

### 4.2 `cells.prescribed_shell@1`: the second geometry

- **The declaration.** `geometry: {law: "cells.prescribed_shell@1", area_m2: {value, provenance}}`.
  The lumen uses the existing `lumen_volume: declared`, with `phases.lumen.volume_L`.
- **The wall is the membrane phase.**
  - Its species (subunits, and free and bound sites) carry no area quanta, so no
    `area_per_leaflet` is declared.
  - Their counts set neither the area nor the lumen.
- **The conductance is declared.**
  - Permeation's encounter is the declared area: a⁺ = P_s·A_sh·ρ0·θ⁺.
  - So the conductance G_s = P_s·A_sh is independent of the wall's counts and of the lumen, and the
    run reports G_s per species.
  - One permeation law serves vesicles and shells, with P_s the same quantity, in m/s.
- **What a shell refuses,** each at the parse with its reason:
  - phase exchange, a join: a prescribed wall takes up no amphiphiles;
  - `lumen_volume: osmotic`: the wall does not swell;
  - `vesicle_floor`, a closure cost and `sigma_max`: no floor, tension or lysis applies;
  - division and shear events: in version 1 a prescribed shell neither divides nor breaks.
- **The rules, one by one:**

  | Rule | For a shell |
  | --- | --- |
  | 1, conditional keys | The shell is a value of the existing `geometry` key. When it is absent nothing is written, so OL1's ids and fingerprints do not move. `exchange_encounter` is required with a geometry but moot for a shell, whose joins are refused: a question for the lead (§10) |
  | 2, directions | Permeation stays an entry. Site binding is declared in one direction only (§4.1) |
  | 3, interfaces | §4.1 |
  | 4–5, area quanta and the floor | No quanta and no floor. No step changes the wall's area |
  | 6–8, the lumen, c_ext and lysis | The lumen is declared. The c_ext check on the pool's declared solutes still applies. There is no lysis |
  | 9–10, division | Refused |
  | 14, streams | No new draws |
  | §0.2e item 3, provenance | `area_m2` and k_on carry their provenance |

- **Dispatch.** The kernel already tests the structure's geometry ID statically, for presence
  (§1). Extending that test to the kind, at the bilayer's direct-import sites, lets bilayer worlds
  trace today's programs, as the presence test keeps OL1's (**S**).
- **Population mode.**
  - Slots hold the wall's places and the lumen's.
  - In version 1, the shell's area and volume are world constants: one shell type per world.
  - The declared-lumen row failure (§1) is fixed first.
- **FR-22's checkpoints carry over,** since the state stays integer counts.

### 4.3 What it lets FR-20's exposed-site control do

- **Today.** Binding from the pool needs a join into the membrane, then a membrane-locus step: two
  steps, with the sites adding area. So "tracer captured on an exposed-site control" is FR-20's
  non-claim (ASSEMBLY_WASHOUT_DESIGN.md:46–52; D240).
- **With S1:**
  - an exposed site binds tracer in one step;
  - a pulse, a pool replacement holding tracer, loads the sites;
  - a washout, tracer-free, keeps every slot's places, and so keeps the bound tracer
    (ASSEMBLY_WASHOUT_DESIGN.md §1, :26–27);
  - the tracer then unbinds into the finite wash bath, from which it can bind again (:35–37).
- **With S2 as well,** the control is a shell whose lumen is closed (P_s = 0) or open. Retention on
  sites and capture in a lumen are then told apart, with the site count, the area and the
  conductance each declared alone.
- **FR-20's operator needs no change:** "Nothing in it is specific to a bilayer"
  (ASSEMBLY_WASHOUT_DESIGN.md:51–52).

## 5. What stays bitwise

- **Every existing version-2 world**, in values, programs and structure. No new key is written
  unless declared, and the new code paths are dispatched statically on the geometry's ID and on the
  step's law.
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
- **New:** `site_binding.py` and `prescribed_shell.py`, in the version-2 package.
- **Changed:**
  - `__init__.py`: the law IDs;
  - `spec.py`: rule 3's admission of site binding, and the shell's refusals;
  - `model.py` and `kernel.py`: the encounter codes, dispatched statically;
  - `world.py`: a wall without area quanta;
  - the bilayer's import sites, for the dispatch: `lumen.py`, `runner.py`, `population.py` (with the
    declared-lumen fix), `records.py` and `division.py`;
  - `interfaces.py`, if the geometry interface gains methods.
- **`src/cells/registry/model_table.py`:** the version-2 rows. The builder edits them, and the F
  owner owns the table's structure (CORE_SEAMS_DESIGN.md §18).
- **Docs:** `validation/assembly_lineages_v2/FORMAT_OL2.md` gains a section, and
  `docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md` gains the rules' rows for the shell and for site binding, as
  a §0.2 ruling entry.
- **Not edited here:** `lean/registry.json` and `lean/COVERAGE.md`. They follow from the Lean
  project's own generator (`lean/scripts/generate_claims.py`), and that project is another agent's.

## 7. Tests (D224)

**Tier 1, rows only:**
- **`tests/unit/test_assembly_lineages_v2_spec.py`** (2 s):
  - site binding is admitted as rule 3's declared encounter;
  - a mass-action interfacial step is still refused;
  - the shell's refusals, one row each: a join, an osmotic lumen, `area_per_leaflet`, a floor,
    `sigma_max`, division and shear.
- **`tests/unit/test_assembly_lineages_v2_registration.py`** (7.6 s): the law and the geometry in its
  exact sets.

**Tier 2, two compiled rows**, each with its seconds and reason stated at the landing:
- **In `test_assembly_lineages_v2_geometry.py`** (28.85 s today; it holds the permeation
  closed-form test):
  - a shell's entry propensity equals P_s·A_sh·ρ0·θ⁺ at two wall compositions and two site counts,
    and it is the same in all four;
  - doubling A_sh while halving P_s leaves it equal to rounding;
  - about 15–25 s more.
- **In `test_assembly_lineages_v2_kernel.py`** (43 s today):
  - site binding's forward and reverse propensities, against k_on·c0·θ⁺·n_S and its reverse from F;
  - at a held pool, the stationary binomial, from the rates' ratio (detailed balance);
  - about 15–25 s more.
- **Planted errors (D187):**
  - a reverse without the site term: the binomial check fails;
  - a shell whose permeation reads W: the equal-conductance check fails.

**FR-20's test file** (the builder's, in progress) **takes one row:** a pulse and washout on a
shell population with exposed sites keeps the bound tracer at the replacement and then releases it
into the finite wash bath. About 20–30 s.

## 8. Acceptance, from the request

1. **A prescribed shell owns a lumen and an exchange conductance.** Its lumen volume and its
   G_s = P_s·A_sh are the declared values, whatever the wall's counts and the site count.
2. **Independent of the membrane's inventory and of its binding-site count.** Changing the wall's
   composition or its site count leaves the entry propensity and the lumen volume unchanged, bit for
   bit.
3. **For FR-20:** an exposed site binds tracer in one step, and a washout keeps the bound tracer.

## 9. Price (S)

| Part | Agent-days |
| --- | --- |
| S1, `cells.site_binding@1`: rule 3's door (parse, kernel code, the reverse from F, labels, registration) | 1–1.5 |
| S2: the geometry dispatch made real at the bilayer's import sites, static by ID | 1–1.5 |
| S2, `cells.prescribed_shell@1`: parse and refusals, the encounter, the run's reports | 1–1.5 |
| The declared-lumen fix in population rows, unless the builder's repairs carry it | 0.25–0.5 |
| Tests | 0.75–1 |
| Docs and FORMAT_OL2.md | 0.5 |
| **S3 in all, development** | **4.5–6.5** |
| S1 alone, with its tests and docs | 1.75–2.5 |
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
2. The conductance: P_s with a declared shell area (recommended: one permeation law for vesicles and
   shells), or a declared G_s per species?
3. One shell type per world in version 1, or per-slot shells?
4. Exposed sites on bilayer vesicles too, with S1 on any geometry (recommended)? And should those
   sites take area?

**For the lead:**
5. Who builds, and when: the origin-of-life builder after FR-20, or another seat under a recorded
   exception?
6. Rule 1's `exchange_encounter` in a shell world, whose joins are refused: required, or absent?
