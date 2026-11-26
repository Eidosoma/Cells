# The engine's output format for OL1's roles (`cells.model.assembly_lineages@2`)

The files describe themselves; this page says where to look. Nothing here needs the engine's code.
The physical choices are the lead's rulings in `docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md` §0.2a (D215,
amended 17 November 2026, twice: "The last molecule" and "The empty common state"; `kept` reworded
18 November 2026) and §0.2b rule 8 (its condition confirmed 18 November 2026). The token names are those of the registered conventions, `ol1_conventions.json`.

## The declared conventions (every bundle and every probe states all six)

| Key | Tokens | Meaning |
| --- | --- | --- |
| `free_energy_form` | `discrete` | F uses ln n! exactly. `continuum` (Stirling's form) is refused by the exact kernel |
| `condensed_measure` | `multinomial`, `multinomial_less_one` | The membrane's measure, with c = 0 (−ln N! + Σ ln n_i!) or c = 1 (−ln (N − 1)! + Σ ln n_i!, G1's measure, the multinomial plus ln N; 0 at N = 0) |
| `membrane_kinetics` | `count_on_m` | A membrane reactant's activity is drawn without replacement, Π ff(n_i, a_i)/ff(N − c, r) at the firing state; the membrane's extent is E(m) = N(m) − c + 1 on the common state m = min(n, n + ν) |
| `lumen_volume` | `declared` | The lumen's volume_L is a constant (OL1's registered worlds have no lumen) |
| `empty_catalyst_phase` | `uncatalysed` | g = 1 where the membrane (the only catalysing phase in OL1) is empty at m |
| `last_molecule` | `kept`, `reversible`, `extinct` | `kept` "gives rate zero only to a pair whose step changes the membrane's count and one of whose end states has an empty membrane. That way the membrane never empties, and nothing else is frozen" (§0.2a, reworded 18 November 2026): a step in which the membrane takes no part fires at its own rate, so a pool step at a probe state with an empty membrane fires at the pool's mass action. `reversible` (c = 0 only): the empty membrane is an ordinary state. `extinct` (c = 1 only): a channel whose result empties the membrane, in either direction, fires at the pair rule's cancelled form, 1/ff(N − 1, r − 1) for E(m)/ff(N − 1, r) (k⁻·1 for the last molecule's leave), has no reverse, and ends the run (status `extinct`); its heat is booked against F_mem(empty) = 0 |

**The empty common state** (§0.2a, as ruled): "Wherever the membrane factor is 0/0, the cancelled
form applies, under every `last_molecule` token. That is the case when a step's common state m has an
empty membrane while neither end state does: a lone molecule changing form, or two joining. It is
the factor's continuous extension, so detailed balance holds as for every other pair." It replaces
the earlier wording, "a pair whose common state has an empty membrane has rate 0".

**`world_role`** (§0.2b rule 8), optional, its one value `probe`: a world declared to be probed.
Under `condensed_measure: multinomial_less_one`, a step with a membrane place on both sides (one
and the same membrane species among both its reactants and its products, as E is in
A + B + E → C + E; its rate +inf where the membrane holds exactly its reactants) is admitted only in
such a world, where a probe reports +inf; any other world declaring such a step is refused at
parse. A step whose membrane species differ between its sides is not singular: at N = r it meets
the 0/0 above and takes the cancelled form. A probe world may be
run, and stops `stalled` at N = r. The role comes only from the registered world file, passed on as
it is: the driver adds nothing to a world record. A role whose world the parser refuses has, in
place of its probe or bundle, `refused.json` with the parser's message.

Dilute phases (the pool, the lumen) take volume-scaled mass action: activity ff(n, a)/X^a and extent
X = N_A V c0, with V in litres and c0 = `standard_concentration_mM` × 10⁻³ mol/L. A held pool
species has activity c/c0, no count and no term in F; its exchanges book reservoir work
w = −Σ ν μ_held, μ_held = μ°_sol + ln(c/c0).

## The rates (every channel)

- **Forward** of step r at state n: a⁺ = k_f · E(m) · g(m) · Π(activities of its reactants at n).
- **Reverse** at state n′: the same law applied to the products, with k⁻ = k_f exp(Σ_p ν_p μ°_p) over
  every place (held ones at μ°_sol), times exp(F_ex(n′) − F_ex(n′ − ν)) for the excess terms
  (regular mixing). This equals the pair rule a⁻(n + ν) = s(m) θ⁺(n) exp(F(n + ν) − F(n) − w).
- **g(m)** = 1 + Σ_j β_rj m_j/N(m), with β = e^ΔΔG‡ − 1, over the membrane at m (1 if it is empty).
- **The membrane factor** E(m)/ff(N − c, r) is (N − c − r* + 1)/ff(N − c, r), with r* the
  direction's net membrane consumption. It is evaluated cancelled, 1/ff(N − c, r − 1), wherever
  r* = r ≥ 1, which is its value at a 0/0 (the empty common state, above). Where a membrane place is
  on both sides (r* < r), under c = 1 the factor is singular at N = r: the rate is +inf there, in a
  `world_role: probe` world only (§0.2b rule 8). A run that reaches such a state stops `stalled`;
  a probe reports +inf.
- k_f is applied after the exponential, so a rate constant scaled by a power of two scales every
  rate exactly.

## The SSA (run.json `ssa`; its `tokens`)

- `tau: neg_log_u1_over_a0` and `select: first_prefix_gt_u2_a0`, over a serial left fold of the
  channels in channel order. Two uniforms per event come from the occupant's event stream (domain
  1, the same derivation and uniforms as `cells.model.assembly_lineages@1`) at counter = the event count.
- **Channels** (run.json `channels`): row r is the forward of step r (trace code +(r+1)); row R + r
  is its reverse (code −(r+1)), each with its reactants and products.
- An event whose time would pass the horizon is not committed.

## A run bundle (ledger_run, replay, other_stream, rescale_pair)

A run whose world the engine's parser refuses (§0.2b rule 8) has, in place of a bundle,
`refused.json`: {format, refused: true, message (the parser's), conventions, rule, and the
provenance of the run it would have been}.

A directory with world.json, run.json, records.npz, resolved_config.json, summary.json and
manifest.json (each file's SHA-256, written last).

- **world.json** (`cells.assembly_lineages.world@2`): {format, id, world, derived}.
  - `world` is the world as the definition states it: units, conventions (the six tokens), species,
    phases, steps, free_energy, rate_factor and founder.
  - `id` is the SHA-256 of its canonical JSON.
  - `derived` holds the places, the offset c, k_BT in joules and ln X of each dilute phase.
- **run.json** (`cells.assembly_lineages.run@2`): format, world (the id), model, engine_models,
  definition_sha256, run {qualifier, start}, `conventions` (the six tokens, echoed), laws (id,
  interface, energy_role, formulas, provenance with works, test), check {probe, world} (the kernel
  identity's verdict), mode, stream, ssa, lifecycle, ledger (conventions and closure), source (the
  engine's revision), end {status, events, time}, time {unit "s", temperature_K, kT_J, horizon_s,
  bases}, places (index, name, species, phase, kind finite or held, held_mM, standard_mu_RT),
  channels, records (every array: file, array, base, axes, unit, kind and what it says), and
  diagnostics.
- **records.npz** (loads with allow_pickle=False):
  - rows: row_time (s), row_event, row_kind (0 start, 1 periodic, 2 end, 3 observed);
    place_count [row, place] in run.json's places order (a held place: 0); reservoir_supplied
    [row, place]; channel_fired [row, channel]; event_heat_kT (Q), reservoir_work_kT (W) and
    free_energy_kT (F at the row, exactly); ledger_residual_kT = Q − [W − (F_t − F_0)];
  - the trace: event_time [event] and event_channel [event] (signed codes);
  - diagnostic: event_uniforms [event, 2] (u1 and u2 of each event).
- **The ledger** closes at every row: F(n_t) − F(n_0) = W − Q, to rounding. A run whose books do not
  close is refused. OL1 has no fission.

## A probe (kernel_probe, boundary_probe, closed_world, wb_ensemble)

**probe.json** (`cells.assembly_lineages.probe@2`) holds:
- format, role, source, and inputs {file, sha256, arrays};
- arrays_sha256 (of probe.npz, as written);
- world {registered file, sha256, engine_world_id};
- conventions (the six tokens) and definition (the engine definition built from the registered
  world);
- places and steps (the registered order of the inputs' arrays) and channels;
- `says`: what each array of probe.npz is.

**probe.npz** holds the outputs, with the registered inputs prefixed `input_`.

- **kernel_probe/<pair>/**, **boundary_probe/<pair>/** (ol1_boundary, the references' amendment)
  and **closed_world/<world>/<pair>/**: a_plus [state, step] (the rate of
  state → state + ν) and a_minus [state, step] (the rate of state → state − ν), from the kernel's own
  rate function. They are 0 where impossible and +inf at a singular state. Also free_energy_kT
  [state] and (kernel_probe) reservoir_work_kT [step], with input_states echoed in the registered
  place order.
- **wb_ensemble/<rung>/<pair>/**: observed [run, time, place] (the state after the last event at or
  before each registered time), events [run], lineage [run], status [run], and
  input_observation_times_s.
  - lineage [run] is each run's own lineage word, and no two runs share one across the whole ladder:
    2000 × (rung index × 2 + pair index) + the run's index.
  - Rungs are in the registered order (m5, m20, m80, m320) and pairs in the order below, so the
    words run 0 .. 15999, consecutive within each block.
  - Seed 1, environment 0 and branch 0 hold throughout. probe.json's `streams` states the block's
    words.
- **refusals/refusals.json**: each registered refusal world with the engine parser's message and
  the `conventions` it was parsed under: the probed pair whose tokens include the world's
  `refused_under`, else the first pair (the file's top-level `conventions`). `all_refused` must be
  true.

`<pair>` is `multinomial__kept` or `multinomial_less_one__extinct`. **roles.json** lists every file
with its SHA-256, the inputs' files and hashes, and the settings that the registered inputs do not
fix: the stream seed (1), the lineage words, the molecule capacity, the chunk, and the ensembles'
event guard.
