# A declared voltage shift on a channel population (FR-64): design note

**Status: a design, written 26 November 2026 at main 4f4a4c34 on branch `fr64-design-20261126`. Nothing is built, and
no `src` or test file changes (D142).**
- **It supersedes** `docs/VOLTAGE_SHIFT_DESIGN.md` on branch `fr64-design` (377a1b34). That note was written at main
  28756b2b, was never merged, and is the note D361 decides on.
- **Its decisions are carried here unchanged,** each marked with its D-number (§14).
- **Every statement about the code is read again at 4f4a4c34.** The rename, the block law's registration, the calcium
  store's channel material term, FR-51's slot refusal and D391 have all landed since 28756b2b.
- Integration grants no acceptance (D143). **S** marks this note's own derivation, done by hand and not run.

**The request** (FR-64 in [FEATURE_REQUESTS.md](FEATURE_REQUESTS.md); D356, D361). D391 freed it to build at normal
priority.
- **In general physics:** a channel population's gates and its open-channel block each read a voltage. The population
  may declare, for each of these readers, that the voltage it reads is moved by a declared function of a local ionic
  condition:
  - the reversal potential of an ion the population carries;
  - or a declared slope per pH unit of the local free proton concentration.
- **What does not change:** permeation, its heat and its charge still read the membrane voltage.
- **The set of shifts is closed.**
- **What it replaces:** FR-51's block `reference` key moves into this declaration with no alias. FR-63's Kv1.5 acid
  shift becomes one use of it, instead of a new law.

**Engine models it runs:**
- `cells.model.resolved_pump_tissue@3` (below, @3), and `cells.model.resolved_pump_composite@1` over it;
- the laws `cells.channel.kv1p5_mh@1`, `cells.channel.kleak_always_open@1`, `cells.channel.naleak_always_open@1` and
  `cells.channel_block.open_channel_block_weighted_modes@1`, all unchanged;
- the free proton read through `cells.kind.rapid_proton_buffer@1` (B4), where a world declares it.

**Read for it:**
- **The code at 4f4a4c34:**
  - `models/surface_pump_v3.py`: `channel_rates`, `channel_kinetics`, `potential_kinetics` and the IMEX loop,
    `channel_block`, `channel_block_terms`, `_patch_slopes`, `block_material_rates`, `channel_material_rates`,
    `_loop_fluxes`, `clamped_channel_flux`, `operator_time_conductances`, `initial_values` and `structure`;
  - `definitions/surface_pump_v3_spec.py`, `models/inner_laws.py`, `models/pump_composite.py` and
    `models/cell_replacement.py`;
  - `laws/channels/open_channel_block.py`, `laws/channels/kv1p5_mh.py`, `laws/electrochemistry.py` and
    `numerics/exponential_gates.py`;
  - `registry/laws.py` (`ChannelLaw`), `registry/species_registry.py` (`check_closure_rows`),
    `kinds/proton_buffer.py`, `kinds/ph_condition.py`, `kinds/species_condition.py` and `analysis/stationary.py`;
- **validation and tests:** `validation/fr51/`, `validation/fr51_two_potassium/engine_check.py`, and the FR-51 and
  calcium-store tests;
- **the notes:** [ID_HIERARCHY_DESIGN.md](ID_HIERARCHY_DESIGN.md) §4, §6 and §7, and
  [MODULE_SYSTEM_DESIGN.md](MODULE_SYSTEM_DESIGN.md) §2.3;
- **the decisions** D327, D345, D346, D351, D353, D355, D356, D361, D371, D377, D391 and D392.

**Words.**
- **A reader** is a part of a population that reads voltage: one gate of its law, or its block. `factors` is already
  the routing door's key (B1), so this note never calls a reader a factor.
- **A shift** is one reader's declared ΔV. The reader reads V_ref = V − ΔV, where V = φ_in − φ_out is the patch
  voltage.

## 0. Summary

| | |
| --- | --- |
| **The mechanism** | Each reader reads V_ref = V − ΔV. ΔV is 0 (nothing declared), or E of a permeant ion (`reversal_of`), or σ (pH − pH_ref) on a declared side (`ph`). ΔV reads concentrations only, never V. Permeation, its heat and its charge still read V |
| **Decided (D361, and the window in the earlier note's §11)** | One optional key on the population: `voltage_shift: {"gates": {"m": shift}, "block": shift}`. Each gate and the block shift separately, and a gate's target and τ move together. σ = dΔV/dpH, in V per pH unit. A required, closed pH window with a 1e-9 pH rounding margin. Sources are carried by the world's registration. All four pairs of reader and kind are admitted, and two have wet-lab evidence |
| **The pieces** | Two frozen shift types in one closed table, the population's `VoltageShift`, a value-free structure entry, the shift's layout fields, and one function, `reader_voltages`. Every site calls that function at the concentrations it already reads (§3) |
| **What the code needs** (read at 4f4a4c34) | The IMEX stage gates go through `potential_kinetics`, which has potentials only. The charge rule and the block's material rule read stored amounts, while the rates read the stage read. The domain check reads V alone. The slot writers rewrite no block or shift field (§2) |
| **Accounting** | The shift changes only multipliers in [0, 1] on fluxes that run down their own gradients. It adds no material, charge or energy, and each population's heat stays non-negative. The block on pH adds one material term (§4) |
| **Migration** | FR-51's `reference` moves to `voltage_shift.block` with no alias, and the old key is refused by name. Frozen files are read through the live driver, as the rename decided (D371 Q7), so FR-51's rows need no fallback (§7) |
| **FR-63** | A `ph` shift on Kv1.5's m gate, on the outside, with each preparation's σ. The size is a two-point secant through each lab's own midpoints, so comparing the engine with those points is circular. FR-63 gets a calibration report, and a registration only on a held-out quantity (§8; question 3) |
| **Bit for bit** | Every world with neither a shift nor a block, in its programs, constants, bindings, records and fingerprints: crossrev's 11 sets and G1's 113 definitions. FR-51's blocked worlds in their values (§9.4) |
| **IDs** | No new ID, family or interface (D361; ID_HIERARCHY §7). @3 keeps its major under MODULE_SYSTEM §2.3 (§11; question 2) |
| **Size** | 4.25 to 5.25 agent-days with the gate, then 0.5 to 1 for FR-63's report (§13) |

## 1. The physics and its sources

**A gate's voltage dependence can move along the voltage axis.**
- Frankenhaeuser and Hodgkin (1957) found that external calcium moves the squid axon's voltage dependence along the
  voltage axis.
- Hille (1968), and Hille, Woodhull and Shapiro (1975), explained such moves under divalent ions and under pH: fixed
  charges near the channel change the voltage its sensor feels.

These works are cited for the idea of a shift along the voltage axis only. They were not read for this note, and the
linear form below is not theirs.

| Work | DOI |
| --- | --- |
| Frankenhaeuser B, Hodgkin AL (1957), The action of calcium on the electrical properties of squid axons. J. Physiol. 137(2):218–244 | 10.1113/jphysiol.1957.sp005808 |
| Hille B (1968), Charges and potentials at the nerve surface. J. Gen. Physiol. 51(2):221–236 | 10.1085/jgp.51.2.221 |
| Hille B, Woodhull AM, Shapiro BI (1975), Negative surface charge near sodium channels of nerve: divalent ions, monovalent ions, and pH. Phil. Trans. R. Soc. Lond. B 270(908):301–318 | 10.1098/rstb.1975.0011 |
| Nernst W (1889), Die elektromotorische Wirksamkeit der Jonen. Z. Phys. Chem. 4:129–181 | 10.1515/zpch-1889-0412 |
| Woodhull AM (1973), Ionic blockage of sodium channels in nerve. J. Gen. Physiol. 61:687–708 (the block law's own source) | 10.1085/jgp.61.6.687 |

The bibliographic details of the first four, and of the three Kv1.5 studies below, were read from Crossref's records
for these DOIs, not from the papers.

**The reversal potential** is Nernst's E_X = (R T/(z_X F)) ln(c_o/c_i). The engine already forms it as a difference of
logarithms, in `open_channel_block.reversal_potential`.

**The pH** is pH = −log10(h / 1 M), where h is the free proton concentration (mM) of the stage's read: the closure's
free h at a buffered node, and the stored row elsewhere.
- **The convention** is the buffer law's (`laws/reactions/rapid_proton_buffer.PH_REFERENCE_mM`, 1000 mM), and
  `cells.kind.ph_condition@1` uses it too.
- **That kind is retiring.** Its docstring names `cells.kind.species_condition@1` as its successor. So the shift reads
  the buffer law's constant directly, and depends on neither kind.
- **It is a concentration, with an activity coefficient of 1.** The shift reads only the difference pH − pH_ref, and a
  world sets h from a measured pH by the same convention at both conditions. So a coefficient that is the same at both
  conditions (at the same ionic strength) cancels (S).

**The linear form is this note's (S).** ΔV = σ (pH − pH_ref) is the secant through one preparation's two conditions,
its control and its acid.
- D351 confirmed only the direction.
- Nothing is claimed between or beyond the two points (§10).
- A saturating titration form would be a new kind of shift, and so a new request.

**The evidence** (D351 and D355; the records are in `/mnt/workspaces/Cells/wetlab-gap-diagnosis-20261124/`):

| Finding | Studies | Status |
| --- | --- | --- |
| Kv1.5's activation moves positive under external acid | Trapani JG, Korn SJ (2003), Biophys. J. 84(1):195–204, doi:10.1016/S0006-3495(03)74842-5; Longobardo M et al. (2001), Br. J. Pharmacol. 134(2):359–369, doi:10.1038/sj.bjp.0704251; Kehl SJ et al. (2002), J. Physiol. 541(1):9–24, doi:10.1113/jphysiol.2001.014456 | Confirmed in direction (D351). The sizes differ about three-fold |
| Kir2.1's block moves with external K, about 1 mV per mV of E_K | Two labs (D355) | Met in direction and in rough size. The composition stays development-only for changes of external K (D356, D391) |

## 2. What exists at 4f4a4c34

### 2.1 Where a population reads voltage

| Site | The voltage it reads | The concentrations it reads |
| --- | --- | --- |
| `channel_rates`: readouts, `explicit_rates`, RK4 through `rhs`, `_loop_fluxes` and FR-34's `clamped_channel_flux` | the patch's V (`channel_voltage`), for the gates, permeation and the block | the stage read's (`physical_amounts(read, p)`) |
| `channel_kinetics` | V: each declared law's `kinetics(voltage, xp)`, called once on the [channel] vector | none |
| The IMEX stage gates: `stage_gates(..., potential_kinetics(potential, p))` | V, from node potentials alone | none, since it has no state |
| An IMEX step's start kinetics, and N2's operator-time prediction | the readouts' `channel_targets` and `channel_tau_s` | the read's, through the readouts |
| `channel_block` and `channel_block_terms` | V − E, where `channel_block_reversal` is set | the caller's |
| `_patch_slopes`, the charge rule (`membrane_rate`, `charge_rows`) | the stage's potentials | **stored** (`physical_amounts(state, p)`) |
| `block_material_rates`, the material rule for laws without their own term | the stage's potentials | **stored** |
| `channel_material_rates`, for laws with a material term such as `cells.channel.cav1p2_m2h@1` | the stage's potentials | the read's |
| `channel_domain_valid`: readouts, `explicit_rates` and `potential_kinetics` | V, on −120 to 60 mV | none |

**What FR-64 must change (S):**
- **The IMEX stage gates never pass through `channel_rates`.**
  - A shifted gate would read V at every stage after the first, while the step's start kinetics read V_ref.
  - FR-64's first reading ("one reference voltage per factor computed in `channel_rates`") misses this path.
- **The charge rule and the block's material rule read stored amounts.**
  - A pH shift at a buffered node must read free h. But the stored proton row there holds the proton equivalents H_eq.
  - **For FR-51's reversal reference this is not a live gap.** Every channel law registered for @3 carries one
    permeant ion, at relative permeability 1. @3's own channels are refused on a closure-held row at either end: by
    B4's `check_definition` for the proton row, and by `species_registry.check_closure_rows` for the general closure.
    So the read and the store agree for that ion.
  - **The parse does admit a reversal of a permeant ion at relative permeability 0,** since `parse_block` checks
    membership only. No registered law has such an ion, but an external or test law could. Such an ion is not moved, so
    a closure could hold it. The material rule's part through E would then use that ion's own zero flux, although the
    other ions' fluxes depend on it (§5; question 4).
- **The domain check reads V alone.**
- **The slot writers rewrite no block field.**
  - `pump_composite.SLOT_WRITERS` lists `cells.operator.scheduled_cell_replacement@1` and `@2`,
    `cells.operator.isopotential_partition@1`, and `cells.operator.scheduled_membrane_insertion@1` and `@2`.
  - They rewrite a slot's law, permeability, patch or activity, and never the block's per-slot fields. So FR-51's
    follow-up refuses them beside a block (`block_slot_errors`).
  - The standalone `cells.model.resolved_pump_replacement@1` runs the composite's check on `composite(spec)`
    (`models/cell_replacement.check_definition`), so it meets the same refusal.
- **What fails closed on a block today:**
  - `initial_values` (`BLOCK_STRUCTURE_REFUSAL`), for a path without the structure;
  - the stationary analysis, keyed on `channel_block_weight`;
  - the parse, for N2 beside a block (`BLOCK_N2_REFUSAL`, FR-51's ruling 5).

### 2.2 How a law declares its inputs

- **`ChannelLaw` declares** `kinetics(voltage, *, xp)`, its gates, its permeant ions, its voltage domain, its RK4
  bound, `stage_term`, `material_term`, and `reads`.
- **`reads` names the closure reads** that a law's own kernels take: B4's free h, or the general closure's. Cycle and
  route laws use it in the same way.
- **No @3 channel law declares a read, and @3 consumes none for channels.** The library page of
  `cells.channel.kv1p5_mh@1` says "Reads: None declared".
- **FR-64 adds no read to any law.**
  - The shift is the population's declaration, and the host evaluates it at the concentrations it already passes.
  - So no law's signature, `reads`, library page or major changes.
  - A law that took concentrations would be D356's rejected alternative (§6, O9).

### 2.3 The pH machinery

- **B4 (`cells.kind.rapid_proton_buffer@1`):**
  - At a buffered node the stored proton row is H_eq. At every stage the read replaces it with free h V. Elsewhere h
    is the stored row.
  - It records `free_proton_mM` and `pH` per node.
  - Its version 1 refuses an @3 channel that moves the proton row at a buffered node.
- **The general closure (`cells.binding.rapid_binding@1`)** names its proton row explicitly (`proton_row`), or has
  none.
- **`cells.kind.ph_condition@1`** reads pH in the same way, and requires its proton row to have valence +1 and to be
  B4's proton row where B4 is declared. FR-64 keeps that rule but not the kind.

### 2.4 Who spells the block's `reference` key

| File | Its state | After FR-64 |
| --- | --- | --- |
| `src/cells/definitions/surface_pump_v3_spec.py`, `src/cells/models/surface_pump_v3.py`, `src/cells/laws/channels/open_channel_block.py` | live | moved (§7) |
| `validation/fr51/engine.py` | live (the ID move edited it) | translates the frozen key at the driver |
| `validation/fr51/closed_forms.py` | live, and reads the frozen spec's own spelling | unchanged |
| `validation/fr51/plants.py` | live | patches the moved names |
| `validation/fr51/references/spec/` (`cases.json`, `LAWS.md`, `README.md`), `validation/fr51/judge.py`, `validation/fr51/REGISTRATION.md` | frozen by tag | never rewritten |
| `validation/fr51_two_potassium/engine_check.py` and its `REGISTRATION.md` | pinned to 955765ef. The registration stopped (D391), and no test runs it | not run on main |
| `validation/fr50/references/spec/cases.json`, case E4 | frozen. FR-50's phase 2 is not built | its future live driver spells the new key |
| `tests/unit/test_surface_pump_v3_populations.py`, `tests/unit/test_calcium_store.py` | live | rows edited (§9.5) |
| `lean/checks/kir_spermine_potassium.py`, `lean/checks/block_concentration.py` | the Lean lane's | told through the user, never edited here |

## 3. The design

### 3.1 The pieces

```python
# laws/channels/voltage_shift.py (new, pure, with no registry record and no ID)
@dataclass(frozen=True)
class ReversalShift:                # {"reversal_of": ion}
    ion: str
    KEY: ClassVar[str] = "reversal_of"
    # delta_v: E = R T (ln c_o - ln c_i)/(z F), FR-51's arithmetic moved unchanged
    # slope:   |dE/dc| = R T/(|z| F c) at each of the two ends

@dataclass(frozen=True)
class PhShift:                      # {"ph": {...}}
    side: str                       # "inside" (the population's cell) or "outside" (its patch's outside node)
    shift_V_per_ph: float           # sigma = d(delta V)/dpH
    reference_ph: float
    ph_window: tuple[float, float]  # closed, with PH_MARGIN
    proton: str = "H"
    KEY: ClassVar[str] = "ph"
    # delta_v: sigma (pH - pH_ref), with pH = -log10(h / 1000 mM)
    # slope:   |d(delta V)/dh| = |sigma|/(h ln 10), on the read side only

KINDS = MappingProxyType({ReversalShift.KEY: ReversalShift, PhShift.KEY: PhShift})  # the closed set
PH_MARGIN = 1e-9  # the window's rounding margin, in pH units (§3.5)

# definitions/surface_pump_v3_spec.py
@dataclass(frozen=True)
class VoltageShift:                 # the population's declaration
    gates: tuple = ()               # ((gate name, shift), ...), in the law's gate order
    block: object = None            # a shift, or None
# FactoredChannelPopulation gains `voltage_shift: VoltageShift | None = None`.

# models/inner_laws.py, InnerStructure
shifted_readers: tuple = ()         # ((channel ID, reader, kind key), ...), sorted; () by default

# models/surface_pump_v3.py
class ReaderVoltages(NamedTuple):
    gates: object                   # [rows, channel] V_r, which is V itself on a row that is not shifted
    block: object                   # [channel] the block's V_ref
    shift: object                   # [reader, channel] delta V, 0 where none
    valid: object                   # h and both ends finite and positive, each pH inside its window
def reader_voltages(ci, co, voltage, p, *, xp, structure): ...
```

- **Each kind is one frozen type** with its parse, its dictionary form, its layout values and its two kernels.
  - The parse, the model and the guard row all read the one table, so the set cannot drift between them.
  - The earlier note had two tables, one in the parse and one in the model (S).
- **The kernels are pure functions in the xp style** of the layout's arrays, as the block law's are.
- **The structure entry is value-free.** It holds which readers shift and by which kind. So only declared kinds are
  traced, and every static switch below reads it.
- **The layout fields exist only where a shift is declared,** as FR-51's do (D148).
  - The reader axis is the structure's gate rows, then one row for the block.
  - FR-51's `channel_block_reversal` and `channel_block_ion` are replaced by the block row of these fields (§7).

| Layout field | Shape | Meaning |
| --- | --- | --- |
| `channel_shift_reversal` | [reader, channel], bool | the reader reads V − E |
| `channel_shift_ph` | [reader, channel], bool | the reader reads V − σ (pH − pH_ref) |
| `channel_shift_row` | [reader, channel], int | the species row read: the ion, or the proton row (0 where none) |
| `channel_shift_outside` | [reader, channel], bool | the pH's side |
| `channel_shift_V_per_ph`, `channel_shift_reference_ph` | [reader, channel] | σ and pH_ref |
| `channel_shift_ph_low`, `channel_shift_ph_high` | [reader, channel] | the window |

Where a reader is not shifted, its entries hold padding that keeps every intermediate finite, as FR-51's padding
does. They are never read, since each kind's mask selects V there.

### 3.2 Where it is declared (decided, D361)

The two examples below use invented values. The pH pair is Trapani and Korn's (§3.5).

```json
{"id": "kv15", "membrane_id": "patch", "kinetic_law": "cells.channel.kv1p5_mh@1", "...": "...",
 "voltage_shift": {"gates": {"m": {"ph": {"side": "outside", "shift_V_per_ph": -0.0234,
                                          "reference_ph": 7.3, "ph_window": [6.8, 7.3]}}}}}

{"id": "kir", "membrane_id": "patch", "kinetic_law": "cells.channel.kleak_always_open@1", "...": "...",
 "block": {"law": "cells.channel_block.open_channel_block_weighted_modes@1",
           "blocker": {"...": "..."}, "modes": ["..."]},
 "voltage_shift": {"block": {"reversal_of": "K"}}}
```

- **Each shift is a one-key mapping that names its kind,** as FR-51's `{"reversal_of": ion}` is. So the reversal moves
  from the block unchanged.
- **The default is omission.** An empty mapping, an empty `gates`, or an explicit membrane-voltage entry is refused
  with "omit it", as `factors` and `ph_conditions` are. One meaning has one spelling, and today's definitions keep their
  fingerprints.
- **Gates are named by the law's own gate names** (`ChannelLaw.gates`), mapped to rows in that order.
- **The type.** A population that declares a shift parses as `FactoredChannelPopulation`, which already carries FR-51's
  `factors` and `block`. `to_dict` writes `voltage_shift` only where it is declared.
- **The key is popped before the strict channel parse,** as `factors` and `block` are.

### 3.3 The four pairs (decided, D361)

| Reader | Reversal (`reversal_of`) | pH (`ph`) |
| --- | --- | --- |
| The block | **Evidence:** external K (D355). Development-only until a registration passes (D356, D391) | Admitted, with no wet-lab claim |
| A gate | Admitted, with no wet-lab claim | **Evidence:** the direction of Kv1.5's acid shift (D351) |

All four pairs are proved as engine arithmetic (§9). Only the two with evidence are named in any library page as having
it.

### 3.4 How each site reads it

| Site | Concentrations | The change |
| --- | --- | --- |
| `channel_rates` | the caller's read, as today | V_r for each gate row, and V_ref for the block, from `reader_voltages` |
| `channel_kinetics` | none | takes [rows, channel] voltages where a gate shifts (below) |
| `potential_kinetics`, at the IMEX stages | **the stage's read (new)** | as `channel_rates` |
| `channel_block`, `channel_block_terms` | the caller's | V_ref and ΔV from `reader_voltages`, and the pH term (§4.2) |
| `_patch_slopes`, `block_material_rates` | **the stage read, for ΔV (new)** | as above |
| `channel_material_rates` | the read, as today | the pH term joins the parts through E |
| `channel_domain_valid` | none | V as today, and each shifted gate row's V_r (§4.3) |
| `clamped_channel_flux` | the read, as today | the block's V_ref at the given V. The gates are the state's, so a gated population's clamped current does not see its gate shifts |
| N2's `operator_time_conductances` | none | unchanged: it reads the start's targets, which are already shifted |

- **Per gate row.**
  - In `channel_kinetics`, a law with no shifted gate row in the world (static, from the structure) is evaluated once
    at V, as today.
  - A law with a shifted row is evaluated once per gate row, at that row's V_r, and each row is taken from its own
    evaluation. That is at most its gate count, two today.
  - A row that is not shifted reads V itself, through `where(shifted, V − ΔV, V)`, and never V − 0. No law changes.
- **The whole gate moves (ruled, D361).** Row r's target and time constant both read V_r. τ's shift follows from the
  form and is not claimed (§10).
- **The IMEX stage gates read the stage's state.**
  - In a world with a shifted gate (static), `potential_kinetics` takes the stage's read concentrations. That is the
    state after the stage's implicit part, the one its explicit rates read.
  - The start kinetics stay the readouts'. So start and stage kinetics come from the one function, each at its own
    state.
  - The last stage has no explicit rates, so its gates take the read alone.
  - Whether the gates share that read with the explicit rates is option O2.
- **The per-stage rules read the stage read.**
  - In a world with a block shift (static), `_patch_slopes` and `block_material_rates` take the block's ΔV from the
    stage read, as `channel_material_rates` already does.
  - FR-51's values do not move. Its reversal ion is never closure-held (§2.1), so the read's rows equal the stored ones
    bit for bit. A world without kinds reads the state itself.
- **The block** is multiplied by u(V_ref) at every site, as FR-51's is today with its reversal.

### 3.5 The pH kind

**The form:** ΔV = σ (pH − pH_ref), and V_ref = V − ΔV.

**The sign. Ruled (D361): σ = dΔV/dpH,** in V per pH unit (`shift_V_per_ph`). Kv1.5's acid shift has σ < 0.
- **Sign check (S).** With σ < 0 and pH below pH_ref, ΔV > 0. Kv1.5's m target is a sigmoid of (V_r + 6.0 mV)/6.4 mV,
  so its midpoint moves from −6.0 mV to −6.0 mV + ΔV: positive under acid, as the three labs report.

**The fields:**
- **`side`, required:** `inside` (the population's cell) or `outside` (its patch's outside node). The evidence is
  extracellular, so neither side is a default.
- **`reference_ph`, required, per shift:** the pH at which the law's own curves hold, the preparation's control.
  Trapani's control is 7.3 and the others' 7.4, so there is no global default.
- **`ph_window`, required:** [low, high], with low < high and the reference inside it. The reference may sit on an
  edge.
- **`proton`, optional (default `H`):** valence +1, and B4's proton row where B4 is declared, as
  `cells.kind.ph_condition@1` requires. Where the general closure holds that row, it must be the closure's declared
  `proton_row`.
- **No `source` field. Ruled (D361):** the world's registration carries the source, as it does for every other declared
  value, FR-51's mode values among them.

**The window's edges. Ruled: a closed window with a fixed rounding margin** (option (c)).
- The lead ruled it in the earlier note's §11 (fc899d3d). D361 records the question and not this ruling, so the
  decision log should record it.
- **Why a margin is needed:** a held bath declared at pH 7.4 reads back 7.4 only to within the rounding of −log10, a
  few ulps (about 1e-15 near pH 7) (S).
- **The rule:**
  - pH is admitted for low − ε ≤ pH ≤ high + ε, with ε = 1e-9 pH units (`PH_MARGIN`).
  - Within ε beyond an edge, the same line applies. Its extrapolation is at most |σ| ε: at most 1e-10 V for any σ up to
    0.1 V per pH unit, about four times the largest of the three labs' σ (S).
  - Beyond ε the step is refused, never clipped.
- **A world whose pH truly leaves the window is refused,** whether by a bath step or an unheld node's drift. Its remedy
  is a wider declared window. That is an extrapolation, and the world's registration owns it.

**Each preparation's pair,** from D351's records. This shows the declaration's shape. FR-63's calibration re-reads the
sources (§8).

| Preparation | Outside pH, control → acid | External K (mM) | Activation midpoint | σ, two-point (S) |
| --- | --- | --- | --- | --- |
| Trapani and Korn 2003, HEK293 | 7.3 → 6.8 | 10 | −15.3 → −3.6 mV | −23.4 mV per pH unit |
| Longobardo et al. 2001, Ltk− | 7.4 → 6.5 | 4 | −14.2 → +3.1 mV | −19.2 mV per pH unit |
| Kehl et al. 2002, HEK293 | 7.4 → 6.4 | 3.5 | −18.3 → −10.5 mV | −7.8 mV per pH unit |

### 3.6 The reversal kind

- **FR-51's arithmetic, moved unchanged.** `reversal_potential` moves from the block law's module to
  `laws/electrochemistry.py`, beside F and R, with the same operations in the same order. So the values stay bit for
  bit.
- **E is the population's own ion's** (FR-51's rule, kept for both readers).
- **New: the ion must be one the population moves,** at a relative permeability above 0 (§2.1; question 4).
- **FR-51's refusal of a block on a reversal for a law with several ions and a material term stays.** It concerns the
  block's material part, and a gate has none.

### 3.7 How it composes with what exists

| Piece | With a shifted gate | With a shifted block |
| --- | --- | --- |
| The routing door's `factors` (B1) | admitted: the factors scale the availability, and the shift moves the reader | admitted |
| FR-51's weighted modes | not applicable | each mode reads the block's one V_ref |
| RK4, and the IMEX tableaux ARS(2,2,2) and others | admitted. RK4 keeps its qualified step, since each V_r stays on the law's domain (§4.3) | admitted |
| N2 (the implicit conductances) | admitted: N2's slopes read the gates' state | refused, as FR-51's ruling 5 refuses any block |
| FR-34's clamp | the gates are the state's | the block reads V_ref at the given V |
| The projective mode | admitted: its settling test reads the shifted `channel_targets` | admitted |
| B4 and the general closure | ΔV reads free h through the read | the same |
| Slot-writing operators | refused (§5) | refused (§5) |
| Other composite operators, such as the bath steps, the water law and labels | admitted. A label row through any channel population is already refused (FR-42) | admitted |
| A compartment's bounding patch | the population is already refused there (refusal 4) | the same |
| The water law | ΔV reads the same c_i and c_o as the population's flux, so it follows the volume wherever the flux does | the same |
| The stationary analysis | refused, failing closed (§5) | refused, as today |

## 4. Conserved accounting

### 4.1 Nothing new is booked

- **The shift moves nothing and books nothing.** It changes only the gates' open fraction and the block's u.
  - Both are multipliers in [0, 1] on each permeant ion's constant-field flux. That flux runs down the ion's own
    electrochemical gradient at V, so each population's heat, Σ_s J_s Δμ_s, stays non-negative (S).
  - The material, charge and energy ledgers keep their forms.
  - This holds for all four pairs.
- **The ion and the proton are read, never moved.**
  - Protons that bind the channel are not counted, as FR-51's blocker is not (trace binding, D356).
  - The gates themselves carry no gating charge or gating energy, today or after.
- **Every reader reads the stage read's free concentrations,** never stored totals (§3.4).

### 4.2 The per-stage rules (S)

| Reader and kind | Charge rule (`membrane_rate`, `charge_rows`) | Material rule (`material_rate`) |
| --- | --- | --- |
| A gate, any kind | No term, as today. Gating slopes are excluded, the exponential update is stable at any step, and the step studies measure them | None |
| The block, no shift | FR-51's T_V | None: FR-51's T_c is zero there |
| The block, reversal | T_V at V_ref | FR-51's T_c,i and T_c,o, with their parts through E, unchanged |
| The block, pH | T_V at V_ref | **New:** for each permeant ion s, \|J_s,free\| β \|σ\| / (h ln 10 V_n), joined to each row the ion moves, at both ends. Held baths are left out. There is no term where the read node is a held bath |

Here β = (Σ_k w_k |a_k| θ_k (1 − θ_k)) / (Σ_k w_k) is FR-51's slope bound (the block law's `slope`), and V_n is the
read node's volume.

**The derivation (S):**
- u = u(V_ref), with V_ref = V − σ (pH − pH_ref) and pH = −log10(h / 1 M). So ∂V_ref/∂h = σ/(h ln 10), and
  |∂u/∂h| ≤ β |σ|/(h ln 10).
- Each ion's flux is J_s = u J_s,free. So |∂J_s/∂n_H| ≤ |J_s,free| β |σ| / (h ln 10 V_n), where n_H = h V_n at an
  unbuffered node.
- At a buffered node the stored row is H_eq, and 0 < dh/d(H_eq/V_n) ≤ 1. So the same expression bounds the slope in the
  stored row: the term is conservative.
- **T_V needs no new term,** since ΔV never reads V, so dV_ref/dV = 1 for both kinds.
- **It follows D327's rule:** the step bound sees every concentration that u reads. Like FR-51's part through E, it is
  an off-diagonal slope, the ion's flux against the proton row. It joins the ion's rows as that part does, in both
  `block_material_rates` and `channel_material_rates`. For every registered law the ion is a single row.
- **For a law with several ions,** the term is per ion (option O3).

### 4.3 Domains at run time

Each check refuses the step, and none clips.
- **V** keeps today's check at its three sites, on −120 to 60 mV.
- **Each shifted gate row's V_r** is checked on the same domain, since the kernel is evaluated there.
  - So a shifted gate narrows the patch voltages at which its population runs, by |ΔV| (S).
  - Kv1.5's τ_m = 8.33 ms − 0.1163 s/V · V is positive only below +71.6 mV (S). The finiteness and range checks read
    the shifted kinetics.
- **The block** keeps its normal-number check (`domain_valid`).
  - For the pH kind, the definition bounds |ΔV| by 0.369 V over the widened window, which is FR-51's admitted reversal.
    So |V_ref| stays within FR-51's 0.49 V, and its normal-number argument holds unchanged.
  - The reversal kind keeps FR-51's checks.
- **pH:** h is finite and positive, and the pH lies inside the window, under its margin (§3.5).
- **E:** both concentrations are finite and positive. @3's domain already keeps every row positive.

## 5. Refusals by name

Each refusal names its reason, and each has one parse row (§9.1).

| Refused | The reason it names |
| --- | --- |
| `voltage_shift` that is not a mapping, is empty, or has keys other than `gates` and `block` | "voltage_shift is {"gates": {...}, "block": ...}; omit it for none" |
| An empty `gates`; a gate name that is not the law's; `gates` on a gate-free law | no such reader |
| `block` on a population that declares no block | no such reader |
| An unknown kind, two kinds on one reader, or an explicit membrane-voltage entry | the closed set (`reversal_of`, `ph`). A combined or new kind is a new request; the default is omitted |
| A reversal of an ion the population does not carry, **or carries at relative permeability 0** (new) | E is the population's own moved ion's |
| A block on a reversal, for a law with several ions and a material term | FR-51's rule, kept |
| A pH shift whose proton row is missing, does not have valence +1, is not B4's where B4 is declared, or is not the general closure's declared proton row where that closure holds it | a pH shift needs the proton row (`cells.kind.ph_condition@1`'s rule) |
| A side other than `inside` or `outside`; a σ, reference or window that is not finite; low ≥ high; a reference outside the window | — |
| On the block: \|σ\| · max \|pH − pH_ref\| over the window widened by ε, above 0.369 V | FR-51's admitted domain allows a reversal of up to 0.369 V, so its normal-number argument holds unchanged |
| A shift on any reader, a gate-only one included, beside a slot writer (§2.1) | these operators write population slots, and none writes a block's or a shift's fields, so a reused slot would read stale values. FR-51's follow-up refusal is widened from blocked populations to every declared shift, in the composite's check. `cells.model.resolved_pump_replacement@1` reaches it through its own `check_definition` |
| The block's old `reference` key | moved, with no alias: the refusal names `voltage_shift.block` |
| A path without the structure (`initial_values`) | it would drop the shift: fail closed, as for the block |
| The stationary analysis on a layout with the shift's fields | it does not read the shift: fail closed, keyed on the shift's own layout field, since a world with only a gate shift has no `channel_block_weight` |
| N2 beside a block, whatever its shift | FR-51's ruling 5, kept |

## 6. Options and recommendations

Each choice below is the lead's to rule, except where a question in §15 asks the user. The choices D361 settled are in
§14.

**O1. Where the kernels live.**

| Option | For | Against |
| --- | --- | --- |
| **A. A pure module, `laws/channels/voltage_shift.py` (recommended)** | One home for the closed set: the types, the ΔV and slope kernels and the margin. The spec, the model, `validation/` closed forms and the tests import one thing. It mirrors the block law's module | One more module with no registry record. A guard must not mistake it for a law home |
| B. Private functions in @3's model module | No new file | The spec's parse and the closed forms would import the model module. The kinds would be split between two places |
| C. A law family (`cells.voltage_shift.nernst_reversal@1` and `cells.voltage_shift.linear_ph@1`) | A provenance record and a library page per kind | A family and an interface for two one-line forms, against D361's "no new ID" and ID_HIERARCHY §7. It is the natural form if the set is ever opened |

**O2. The stage read at the IMEX stage gates** (worlds with a shifted gate only, static).

| Option | For | Against |
| --- | --- | --- |
| (a) The gates take their own stage read | The least change | Where kinds declare a stage read (B4's root solve), each stage solves it twice |
| **(b) One read per stage, shared by the stage gates and the explicit rates (recommended)** | One solve. The gates and the rates are seen to read one state | `explicit_rates` gains an optional `read` argument. The cost is measured (D142) |
| (c) ΔV frozen at the step start | The cheapest | It differs from the block's ΔV, which `channel_rates` takes at the stage, and it is first order in a moving shift. Rejected |

**O3. The block on pH, for a law with several ions.** (a) **A term per permeant ion (recommended):** each ion's flux
depends on h through u, and each term is computable. (b) Refuse it, as FR-51 refuses the reversal for a law with
several ions and a material term. FR-51 refuses because its part through E is the named ion's flux alone. The pH term
has no such limit, so (b) would refuse a case the rule can bound.

**O4. A readout column for ΔV.** (a) **None in version 1 (recommended):** ΔV follows from each row's recorded
concentrations, and at a buffered node from B4's recorded `pH`. (b) `channel_voltage_shift_V` [reader, channel], only
where a shift is declared, as `channel_unblocked_fraction` is only where a block is. It is cheap to add later if FR-63's
report or an audit needs it.

**O5. The key move and @3's major.** This is question 2, argued in §11.

**O6. The slot writers.** (a) **Widen FR-51's refusal to every declared shift (recommended):** fail closed, with one
check. (b) Each slot writer rewrites the shift's fields from its templates. That changes every slot writer, which other
owners hold, and waits for a world that needs a shift beside them.

**O7. A reversal ion at relative permeability 0.** This is question 4. Refusing it narrows FR-51's admitted domain by a
case no registered law reaches.

**O8. FR-63's qualification.** This is question 3 (§8).

**O9. Considered and not taken:**
- **A shift-source kind.** A node-level kind would expose ΔV per source, and a population would name a source per
  reader, as the routing door names factor sources.
  - For: it reuses the kind contract, and one source could serve several populations.
  - Against: the reversal is per population, of its own ion at its own two nodes, and fits no node source. A kind is a
    new ID (against D361). It would need feedback hooks for the material rule.
- **A law per channel and kind** (FR-63's first form): D356 chose the mechanism instead.
- **Laws that read concentrations** through `ChannelLaw.reads` and a wider `kinetics` signature: every parity law's
  signature would change, against "parity laws are untouched" (D356).

## 7. The migration of FR-51's `reference`

**The engine:**
- **The declaration.**
  - The block loses `reference`. `{"reversal_of": ion}` moves unchanged to `voltage_shift.block`, and
    `membrane_voltage` becomes omission.
  - The old key is refused at parse, naming its new place, as D345 refuses old IDs.
  - `ChannelBlock` loses `reversal_of`, and `BLOCK_KEYS` loses `reference`.
- **The block's model code.** `channel_block` and `channel_block_terms` take the block's V_ref and ΔV from
  `reader_voltages`. `ChannelBlockValues.reversal` becomes `shift`.
- **The layout.** `channel_block_reversal` and `channel_block_ion` give way to the block row of the shift's fields.
- **The block law's module keeps the fraction's mathematics only.**
  - `MEMBRANE_VOLTAGE` goes with the key, and `reversal_potential` moves to `laws/electrochemistry.py`, unchanged.
  - Neither is a field of the law's record (`ChannelBlockLaw`, `BLOCK_KERNELS`).
  - Its docstring's V_ref line and its library page now read: "the voltage the population's declared shift gives the
    block (FR-64)". `UNBLOCKED_FRACTION_NOTE` changes in the same way.
  - The scope lines (external K only; D355) stay.

**Frozen files are read through the live driver, as the rename decided** (D371 Q7: "translate", with the engine
strict).
- **`validation/fr51/engine.py`** is live, and already copies `cases.json`'s `reference` into the declaration. Its
  `_block_declaration` now writes the shift instead: `voltage_shift.block` for a reversal, and nothing for
  `membrane_voltage`.
- **`closed_forms.py`** reads the frozen spec's own spelling and stays as it is. **`plants.py`** patches the moved
  function and fields. **`judge.py`** and `references/spec/` are frozen and untouched.
- **So the earlier note's fallback is retired.** That fallback added about 20 host rows if the tagged files could not
  be read on the new key. Every FR-51 row reads its cases through `engine.py`, as do both compiled files, so the rows
  pass on the new key with no new rows.

**Other consumers:**
- **FR-51's two-potassium engine check** (`engine_check.py`) declares the old key. It is pinned to 955765ef, the
  registration stopped (D391), and no test runs it. It stays as recorded and is not rerun on main.
- **FR-50's phase 2.** Its frozen case E4 declares a block on the K reversal. Phase 2 is not built, so its live driver
  translates the key when it is written.
- **The tests.** FR-51's reversal-ion refusal row moves into the shift's refusal table. The round-trip and slot rows
  drop `reference`. `tests/unit/test_calcium_store.py`'s `block_of` helper writes the new key, and its four rows keep
  their meaning.
- **The Lean lane.** Its drivers `lean/checks/kir_spermine_potassium.py` and `lean/checks/block_concentration.py`
  declare the old key. After the move the engine refuses it, naming the new place. The change reaches the Lean lane
  through the user, as the rename's table did.
- **Records under `/mnt/workspaces`** are never rewritten. FR-51's judged record stays as it is.
- **The proof, once, at the build:** FR-51's judge runs on the translated driver. Its verdict must be D377's (every
  criterion passing, all eleven plants caught), and its engine values must be bit for bit the base's.

## 8. FR-63 under this mechanism

- **No new law.** Kv1.5's acid shift is `voltage_shift.gates.m`: a `ph` shift on the outside, with each preparation's
  σ, control pH and window from its own pair (§3.5).
  - `cells.channel.kv1p5_mh@1`'s code is untouched.
  - Its library page gains the scope line D351 asked for, pointing to this declaration.
- **The parity law's own control is not any preparation's.**
  - Its m midpoint is −6.0 mV, against the controls' −15.3, −14.2 and −18.3 mV.
  - The shift moves the law's curve by ΔV and does not align it to a preparation. Aligning the control would need a
    constant shift, which is not in the closed set.
  - The report states each preparation's offset.
- **Why a wet-lab comparison of the size would be circular (S).**
  - σ is the secant through each lab's own two midpoints. So the engine's midpoint shift at the acid pH is ΔV, which is
    the measured shift by construction.
  - Its sign is the data's sign, so the direction across the three labs holds by construction too.
  - What such a comparison tests is arithmetic, which §9 already proves.
  - A wet-lab claim needs a quantity that was not used to set σ. Examples are a third pH level within one study, or
    another readout of the same preparation.
  - Lean's claim file marks Trapani and Korn's 75 ms step (Fig. 1B) as held out (`lean/claims/kv15-ph-activation.md`).
    Whether it is unscored is Lean's to say.
  - Any such prediction also carries the parity law's control offset and τ's unclaimed shift, so it would test the
    parity law with the shift, not the shift alone.
- **The recommendation (question 3):**
  - FR-63 becomes a calibration report, with no registered comparison: each preparation's σ, its protocol replayed with
    the declaration, the replayed midpoint shift against the measured one, and the direction.
  - The replay is not exactly ΔV, since h reads V and inactivates during each prepulse. That difference is reported as
    what the form implies.
  - **Reported, not judged:** the K–pH interaction (an indication pair, D351), and the acid loss of maximal conductance.
    D351's records transcribe Kehl et al.'s acid/control maximum conductance as 0.19, 0.56 and 0.81 at 0, 3.5 and
    140 mM external K.
- **The acid loss of maximal conductance needs no new mechanism, if a world wants it.** It can be declared as a routing
  door factor, with `cells.kind.species_condition@1` reading the outside proton row. That is outside FR-63 and is not
  claimed. Its value would be one lab's indication.

## 9. The acceptance plan

A plant is the engine with one planted change, and each must fail its row. All four pairs are proved as engine
arithmetic. The closed forms are written in 50-digit decimals, in `validation/`, from the formulas in §1 and §4.2, never
from the engine's kernels.

### 9.1 Shared rows

| Row | Claim | The cheapest proof | Plants | Cost |
| --- | --- | --- | --- | --- |
| Default | A world with neither a shift nor a block keeps today's program | crossrev's 11 sets and G1's 113 definitions, identical (the gate). One round-trip row: no key, with today's type, structure, layout type and fingerprint | — | the gate, and one row |
| Zero size | A zero shift is no shift, and neighbours are unchanged | σ = 0 on a gate and on the block: the readouts, explicit rates, one IMEX step and one RK4 step are bit for bit the unshifted population's values. A reversal at c_i = c_o: that state's readouts and explicit rates are bit for bit (the step's own flux then moves c_i). A second, unshifted population is bit for bit unchanged | the reader mask dropped | about 2 s |
| Stage state | The IMEX stage gates read the stage's state, at its V_r | One host IMEX step with a gate shifted by E of the cell's own ion, so E moves within the step. At each stage, the captured stage kinetics are bit for bit the kernel at V − E of that stage's read | the step start's state; the stage gate at V | about 1 s |
| Refusals | §5 | One parse row each, in one parametrized table. The slot writers take rows in FR-51's parametrized slot test, with a gate-only shift: on the composite form, and on the standalone `cells.model.resolved_pump_replacement@1` | each refusal planted away is admitted | milliseconds each |
| Round trip | Shifted definitions round-trip | alone, and beside `factors` and a block | — | under 1 s |
| Closed set | The table's two kinds each have a ΔV kernel, a slope kernel, their refusals and their plants | one guard row | a third kind added to the table alone | milliseconds |
| Migration | FR-51 is unchanged | FR-51's rows through the translated driver; the old key's refusal row; FR-51's judge once at the build (§7) | FR-51's own plants, moved | no new rows |

### 9.2 Each pair

| Pair | Closed forms (host) | Per-stage rule | Plants |
| --- | --- | --- | --- |
| A gate on pH (evidence: direction, D351) | ΔV across the window, on both sides. m∞'s midpoint is −6.0 mV + ΔV. **A test double:** at a held bath, so ΔV is constant, the shifted population is bit for bit a twin running a code-99 test law, Kv1.5's kernel with m's row at V − ΔV. Compared: the readouts, the clamped flux, one RK4 step, and one IMEX step with and without N2. ΔV at a B4-buffered node, from free h | none | **the stage gate at V, through `potential_kinetics`**; **the stored H_eq in place of free h at the buffered node**; the sign flipped; the other side read; h without the 1 M reference; τ read at V; h's row shifted too; the shift leaking into permeation |
| A gate on the reversal (admitted) | the targets and τ bit for bit the kernel at V − E. ΔV = E at two concentration pairs | none | the stage gate at V (the stage-state row); E's valence sign flipped; c_i and c_o exchanged |
| The block on the reversal (evidence: external K, D355) | FR-51's rows, through the driver | FR-51's T_V and T_c, criteria G and E | FR-51's own plants, moved |
| The block on pH (admitted) | u at V_ref within B-u's 1e-12, on both sides, across the window | T_V bounds dI/dV within G's band. The new term bounds \|∂J_s/∂n_H\| within E's band, at an unbuffered and at a buffered node. The 0.369 V bound is admitted at the limit and refused just above it | the term dropped; **the term read from the stored H_eq at the buffered node**; the sign flipped; the bound unchecked |

- **The two gaps of §2.1 each have plants:**
  - the stage gate at V, caught by the test double, the stage-state row and §9.3's item 5;
  - the stored total in place of free h, caught by the buffered-node rows in ΔV (a gate on pH) and in the new term (the
    block on pH).
- **At an unbuffered node the stored row is the free one,** so only the buffered-node rows see that plant (S).

### 9.3 The composed world (compiled)

Only a compiled IMEX run reaches the stage path with the static switches traced, so the world runs IMEX with shifted
gates, and carries one population per pair.
- **The world:** `cells.model.resolved_pump_composite@1` over @3, ARS(2,2,2), one cell on a held bath, with B4 at the
  cell (one buffer). Its populations:
  - **P1, a gate on pH:** Kv1.5, whose m reads the bath's pH;
  - **P2, a gate on the reversal:** a second Kv1.5, whose m reads V − E_K;
  - **P3, the block on the reversal:** the Kir composition, `cells.channel.kleak_always_open@1` with FR-51's block on
    the K reversal;
  - **P4, the block on pH:** `cells.channel.naleak_always_open@1`, whose block reads the cell's pH. The cell is
    buffered, so the read is B4's free h, and the new material term is evaluated away from a held bath.
  - **The bath steps:** one neutral step in K, then one in pH, by `cells.operator.scheduled_bath_composition@1`, which
    refuses net-charged steps.
- **The values** are fixed at build time so that each reader sits where its shifted and unshifted values differ by
  much. For example, the K step brings the resting V near m's midpoint.
- **On every observed row:**
  1. every host check passes, the ledgers included;
  2. each population's cumulative heat does not decrease;
  3. P1's and P2's recorded `channel_targets` and `channel_tau_s` equal the kernel at each one's closed-form V_r (m)
     and at V (h). ΔV comes from the row's recorded concentrations;
  4. P3's and P4's recorded `channel_unblocked_fraction` equals the law at the closed-form V_ref, within 1e-12
     relative. P4's pH is B4's recorded `pH`;
  5. **the stage path:** after each bath step, at rows where the cell has settled, the gate shifted by that step equals
     m∞(V_r), within a bound well below |m∞(V_r) − m∞(V)|/2. The bound and the settling test are fixed from the run's
     own rows before any plant runs.
- **Item 5 is the one that reaches the stage path,** since items 3 and 4 read the readouts.
  - `exponential_gates.advance` mixes the start and end targets. So a gate whose stage targets read V settles at
    m∞(V_r) + (m∞(V) − m∞(V_r)) f(z), where f(z) = 1/(1 − e^−z) − 1/z and z is the step times the mean of the two end
    rates.
  - f runs from 1/2 at small z toward 1, so such a gate lies at least halfway toward m∞(V) (S).
- **Across the run:**
  - a restart from mid-run is bit for bit;
  - the composite's clamped entry point equals @3's at one row;
  - step and compile time are reported against the same world with no shift (D142).
- **Plants,** each failing the item named:
  - the pH sign flipped (items 3 and 4);
  - the other side's pH read (items 3 and 4, after the pH step);
  - ΔV frozen at the initial state (item 3 or 4, after the bath steps);
  - the stage path at V (item 5);
  - the stored H_eq in place of free h, in `reader_voltages` (item 4, at the buffered cell). The same plant in the
    per-stage rules alone is the host row's (§9.2).

### 9.4 What must stay bit for bit

| What | What stays | How it is shown |
| --- | --- | --- |
| **Every world with neither a shift nor a block** | its programs (jaxpr text), constants, bindings, records, definition and fingerprint | the gate: crossrev's 11 sets, G1's 113 saved definitions, and the judges' derivative programs and the worlds outside crossrev that D395's gate compared. No new test is needed. Every new line sits under a static test of the structure or the layout type, as FR-51's `_has_block(p)` does |
| A population with no shift, in a world that has one | its values | the zero-size row's neighbour (§9.1) |
| A zero shift (σ = 0) | the values of the same population without a shift, over whole steps | the zero-size row |
| A reversal at c_i = c_o | that state's readouts and explicit rates | the zero-size row |
| **FR-51's blocked worlds after the move**, under both references: the judged cases, the RUN world and the calcium store's blocked rows | their values: every judged quantity, RUN's rows and the compiled ends | FR-51's tests through the translated driver, and its judge once at the build |
| Their programs, definitions and fingerprints | these change, since the layout's two block fields become the shift's and the definition's key moves | compared by values, as D361 recorded |

**FR's renewed baselines** (D396's permanent folder) contain no shifted world. A blocked baseline, if any, is compared by
values. The gate's FR scripts read it as they do today.

### 9.5 Test cost (D224)

- **The host rows:**
  - about 40 rows and their plants go into `tests/unit/test_surface_pump_v3_populations.py`, where FR-51's host rows
    are. That file is tier 2, measured at 62 tests in 23.5 s;
  - about 15 of them are parse refusals in one parametrized table, which take milliseconds;
  - the slot writers' rows join FR-51's parametrized slot test;
  - the rest add about 20 to 30 s, so the file stays well under the 90 s cap. There is no new host file.
- **The edited rows** are §7's: FR-51's reversal-ion row, its round-trip and slot rows, and the calcium store's
  `block_of` helper.
- **The compiled world** is one composed world in its own file.
  - FR-51's two compiled files take 67 s and 65 s, so adding the world to either would pass the cap.
  - The estimate is 60 to 80 s. It states its seconds and its reason at landing (D224). It is tier 2 if it measures
    under the cap (question 5).
- **The tiers are measured again after landing.**

## 10. What it does not claim

- **The internal-K indication (D355).** The reversal kind moves the block 1 mV per mV of E for internal changes too. It
  predicts −36.3 mV where Lopatin and Nichols saw about +5 mV, in one study. It is supported for changes of external K
  only.
- **The gates on the reversal:** admitted, with no wet-lab claim. No gate on V − E has evidence here (D356). Kir2.1 is
  `cells.channel.kleak_always_open@1` with FR-51's block on the K reversal, and `cells.channel.kir2p1_mh2@1`'s gates
  read V.
- **The block on pH:** admitted, with no wet-lab claim.
- **Kv1.5 under acid, beyond the midpoint's direction:**
  - **the linear form,** a secant between each lab's two conditions. Nothing is claimed between them or beyond them;
  - the size per pH unit, which is calibrated per preparation;
  - **the parity law's control midpoint,** which is not any preparation's (§8);
  - a shift of inactivation, since h declares none;
  - **τ's shift,** which the whole-gate form implies: unclaimed and unjudged. D351 confirmed the activation midpoint
    only. Its records hold one preparation's slower activation at +60 mV (Longobardo et al.), a single lab's reading;
  - the acid loss of maximal conductance, and the K–pH interaction, an indication pair.
- **Mechanism:** ΔV is a declared displacement. Nothing is claimed about surface charge or titratable residues.
- **Activity:** the pH is a free concentration against 1 M, with a coefficient of 1 (§1).

The library pages of `cells.channel.kv1p5_mh@1` and of the block law say the same.

## 11. IDs and majors (MODULE_SYSTEM §2.3; D345, D346, D371)

- **No new ID.** FR-64 is a declaration on the population, part of @3's channel-population schema, as `factors` and
  `block` are.
  - ID_HIERARCHY §7 lists it as "FR-64's shift, a declaration with no ID".
  - Its keys (`voltage_shift`, `gates`, `block`, `reversal_of`, `ph`) are schema keys.
  - D346's closed list of families is unchanged.
- **§2.3's rule:** "an idle optional field keeps the major; a change of meaning takes a new one". Read against it (S):
  - **`voltage_shift` is idle where omitted.** No type, layout, program, record or fingerprint of any other world
    moves. So it keeps @3's major, as FR-51's `block` did.
  - **The key move changes a spelling, not a meaning.** Every FR-51 definition keeps its V_ref arithmetic bit for bit.
    Only the place of its declaration moves, and the old place is refused with a message naming the new one.
  - **This is the rule the rename applied to 386 spellings:** no aliases, old spellings refused by name, majors kept
    (D345).
  - **The stricter reading:** a definition valid yesterday is refused today under the same ID, so the schema changed.
    That reading would make @3 into @4.
  - **The pre-alpha rule answers it:** no backwards compatibility (the user, 22 November). Past runs are reproduced
    from their tags and snapshots, whose revisions they record. So the recommendation is to keep @3 (question 2).
- **The block law keeps @1.** Its record (`ChannelBlockLaw`: its five kernels, ranges and sides) is unchanged.
  `MEMBRANE_VOLTAGE` and `reversal_potential` are module names outside the record.
- **`cells.channel_block_law@1` and `cells.channel_law@1` are unchanged.** No kernel signature changes, and `reads`
  stays `()` on every channel law.
- **Kv1.5's, the leaks' and Kir2.1's code and majors are unchanged.**

## 12. Files it touches

- **The engine:**
  - `src/cells/laws/channels/voltage_shift.py` (new, O1 A): the closed set's types and kernels, and the margin;
  - `src/cells/definitions/surface_pump_v3_spec.py`: the parse, `to_dict`, `VoltageShift`, the population type's
    field, the block's lost key and its refusal, and the module docstring's schema;
  - `src/cells/models/surface_pump_v3.py`: the layout fields and their initial values; `reader_voltages`;
    `channel_rates`, `channel_kinetics` and `potential_kinetics` with the IMEX loop's stage read; the block's values and
    terms; `_patch_slopes`, `block_material_rates` and `channel_material_rates`; `channel_domain_valid` at its three
    sites; the fail-closed check in `initial_values`; the structure's entry; the record notes;
  - `src/cells/models/inner_laws.py`: `InnerStructure.shifted_readers`, a recorded exception there, as FR-51's was;
  - `src/cells/models/pump_composite.py`: the slot refusal, widened to every declared shift;
  - `src/cells/laws/channels/open_channel_block.py` and `src/cells/laws/electrochemistry.py`: §7's move;
  - `src/cells/analysis/stationary.py`: the refusal.
- **Validation:** `validation/fr51/engine.py` (the translation) and `validation/fr51/plants.py` (the moved names).
- **Tests:** `tests/unit/test_surface_pump_v3_populations.py` and `tests/unit/test_calcium_store.py` (rows), one new
  compiled file, and `tests/test_tiers.json` (measured again).
- **Docs:** `docs/library/cells/laws/channel.kv1p5_mh@1.md`,
  `docs/library/cells/laws/channel_block.open_channel_block_weighted_modes@1.md`, and FR-63's and FR-64's entries in
  `docs/FEATURE_REQUESTS.md`. FR-64's entry still points to the earlier note; the lead points it here when this note
  lands.
- **Not touched:** any law's kinetics; every frozen file of §2.4; `lean/`.

## 13. Size and order (S)

| Work | Agent-days |
| --- | --- |
| The parse: `voltage_shift`, the two types, the refusals, `to_dict`, and the block's lost key with its refusal | 0.5 |
| The kernels' module, and the move of `reversal_potential` | 0.25 |
| @3's plumbing. The structure entry, layout fields and `reader_voltages`; `channel_kinetics` per row and `channel_rates`; the block's values and terms; the IMEX stage path and its shared read. The per-stage rules on the read, with the pH term in both places; the domain checks; the fail-closed sites; the widened slot refusal | 1.5 to 2 |
| The migration: FR-51's driver and plants, the edited rows, the library pages and the spec's docstring | 0.5 |
| The tests: about 40 host rows with their plants, and the composed compiled world | 1 to 1.25 |
| The gate and the review's fixes. The gate is tiers 1 and 2, crossrev, G1, FR's baselines, and FR-51's judge once | 0.5 to 0.75 |
| **FR-64** | **4.25 to 5.25** |
| FR-63's calibration report: three preparation worlds, each lab's protocol replayed, and the report | 0.5 to 1 |

**The order:**
1. This note lands, with no `src` change, together with the lead's rulings and the user's answers.
2. FR-64 is built on one branch, with one gate.
3. FR-63's calibration report follows FR-64's landing. A registration follows only if question 3 finds a held-out
   quantity.
4. FR-50's phase 2, whenever it is built, spells the new key in its live driver.

## 14. Decided

**By the user** (D361):
- FR-64's priority is normal.
- All four pairs of reader and kind are admitted, and only the two with evidence are claimed. The plan proves all four
  as engine arithmetic.

**By the lead,** as the earlier note recommended:
- **The readers** (D361): each gate and the block separately. A gate's shift moves its target and τ together.
- **The pH sign** (D361): σ = dΔV/dpH, in V per pH unit, negative for Kv1.5.
- **The sources** (D361): the world's registration carries them.
- **The timing** (D361): the build waits for FR-51's follow-up and the rename. Both have landed, and D391 freed the
  build.
- **The window: option (c).** This was ruled in the earlier note's §11 (fc899d3d) and is not in the decision log. The
  window is required and closed, with a fixed margin of 1e-9 pH units for rounding only. A world whose pH truly leaves
  it declares a wider one, and its registration owns the extrapolation.
- **The slot writers** match `SLOT_WRITERS`, and the standalone replacement model needs no check of its own (the
  earlier note's §11).

**By the rename** (D371):
- **Q2:** the block law has its own family, `channel_block`, and is registered. This is done.
- **Q7:** frozen files are read by translation at the live driver, with the engine strict. §7 applies it to FR-51's
  `cases.json`.

**Rulings this note asks of the lead:** O1 (A), O2 (b), O3 (a), O4 (a) and O6 (a).

## 15. Questions for the user

1. **Which note lands.** This note re-reads the code at main 4f4a4c34 and carries D361's decisions unchanged. Land it in
   place of the earlier `docs/VOLTAGE_SHIFT_DESIGN.md`, and leave that note's branch, `fr64-design` (377a1b34),
   unmerged as history? **Recommended: yes.**
2. **@3's major under MODULE_SYSTEM §2.3.** Keep `cells.model.resolved_pump_tissue@3`, and the block law's @1, and
   refuse the block's old `reference` key by name, as D345 refuses old IDs? **Recommended: yes.** The move changes a
   spelling and not a meaning, the rename did the same for 386 spellings, and the pre-alpha rule rules out an alias
   (§11).
3. **FR-63's qualification.** FR-63 would get a calibration report with no registered comparison, since σ is the secant
   through the same two midpoints a comparison would judge (§8). A registration would follow only if a held-out
   quantity exists. Should that be the course? **Recommended: yes.** Ask the Lean lane, through the user, whether any of
   the three studies has an unscored third pH level, or an unscored readout of the same preparation, such as Trapani and
   Korn's held-out 75 ms step. Any registration would also have to own the parity law's control offset.
4. **A reversal of an ion that the population does not move.** Refuse a reversal, on a gate or on the block, of a
   permeant ion at relative permeability 0? Its material part through E would use that ion's zero flux, while the other
   ions' fluxes depend on it. No registered law has such an ion, so no world changes. **Recommended: yes.** It narrows
   FR-51's admitted domain by a case none of its registered cases reaches.
5. **The compiled world's tier.** The composed world is the only compiled proof of the stage path, of the free-h read
   and of conservation across all four pairs. Should it be its own tier-2 file, at an estimated 60 to 80 s, with its
   seconds stated at landing? Or should it run weekly in tier 3, with the host rows as the gate?
   **Recommended: tier 2** if it measures under the 90 s cap, and tier 3 otherwise.
6. **The build.** FR-64's build is 4.25 to 5.25 agent-days on one branch with one gate, and FR-63's report 0.5 to 1
   more. Start them at normal priority, in the queue order you set (D392)? **Recommended: yes,** after the items you
   have ranked above them.
