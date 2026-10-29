# Static tissue profiles to resolved physical definitions

The bridge `cells.core.tissue_profile_preparation.prepare` accepts direct
`resolved_tissue@1` or `resolved_tissue@12` definitions, explicit `Geometry`,
the frozen native default/ordered `Profile` objects, and six native ion-enable
booleans. It returns a validated `Preparation(definition, provenance)`.
`replay`, `write_preparation` and `read_preparation` retain a complete deterministic
source/profile/geometry recipe and refuse stale or inconsistent data.
No shared model dispatch or solver changes are required.

Geometry contains the actual frozen-profile `Layout`, thickness in metres for
every membrane ID, reciprocal partner membrane IDs, one oriented membrane pair
per physical junction ID, exact original neighbor IDs and explicit provenance.
Every cell/membrane/exterior and inside/outside owner must match the actual
resolved model. Non-boundary contacts must map bijectively onto its physical
junctions, with the correct sender/receiver cells. Missing, asymmetric, duplicate
or ambiguously aggregated contacts are refused. Boundary membranes self-pair.
Thickness is never inferred from volume or capacitance. Non-SI length labels,
nonpositive or nonfinite geometry and nonunit native rho are refused.

The source equation uses D/d, the simulation passes d=p.tm and initializes
rho_channel=1, and update_Co multiplies area flux by membrane area. The resolved
Cells constant-field law uses area*P and converts mol/s to fmol/s. Therefore:

- P[m/s] = D[m2/s] / membrane_thickness[m].
- Native inward mol/(m2*s) becomes negative Cells outward fmol/s after multiplying
  by area[m2] and dividing by 1e-15.
- fmol/pL and mol/m3 have the same numerical concentration value.

The native electroflux return docstring says mol/s; its actual expression and
update_Co caller establish area flux. Unit evidence executes the authenticated
unchanged native function at common explicit F/R/T inputs and compares Cells
flux and independent 80-digit Decimal equations. This establishes coefficient,
area, amount and direction correspondence. Cells physical constants are kept;
it is not a calibration to rounded native parameter defaults.

The bridge calls the frozen native profile selector, ordered-diffusion and
insular-weight kernels unchanged. Default always means ALL and insular; source
percentage mutations/ALL aliases and repeated occurrence order remain in the
binding manifest. Later profiles overwrite enabled-ion membrane coefficients;
all overlapping insular blockers combine, so a later profile cannot reconnect
an earlier barrier. Raw image inputs are decoded F pixels, as in the component;
asset decoding remains caller-owned.

Enabled physical profile ions are Na, K, Cl and Ca with their actual valences.
Unsupported or absent enabled ions are refused. Disabled model species remain
untouched by membrane conversion. An insular edge is a whole physical route:
all its species permeabilities become zero while its ID, intrinsic gate,
schedule, area and other parameters remain. Nonblocked edges remain exact.
Only listed selected permeability fields may differ. The bridge validates the
emitted definition, compares every initial state field and refuses any inferred
initial-state change. Inventories, charges, IDs, volumes, states, channels,
capacities, clocks and all other parameters remain the source values.

The provenance includes the canonical source definition, all profiles/selectors,
explicit percentage permutations/decoded pixels, layout and geometry, target
occurrences, native kernel identity, unit derivation, ordered field changes and
initial-state identity. Replaying the recipe must reproduce both definition and
provenance. This is a preparation artifact, not a solver checkpoint or cut epoch.

Dynamic interventions, pressure, ECM transport and nested fuel/regulation/cut
models are outside this direct static preparation interface. Native geometry
rebuilding, RNG-stream equivalence and full simulator parity are separate.
The old native profile component, physical kernels and earlier evidence stay
frozen. Tests qualify the bridge, independent component composition and source
unit correspondence on CPU7; no GPU or compiled trajectory work is claimed.
The machine receipt owns exact evidence/resource counts and examples. No
shared/PROGRESS edits, detached-job polling or automatic follow-up occurred.
