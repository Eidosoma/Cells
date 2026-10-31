# Supplied INIT to SIM transition — held source preparation

The separate `betse_normal_ecm_init_sim_transition` adapter accepts an explicit
`CompleteInit` artifact from an exhausted original INIT calendar. `bind` admits
new SIM parameters, fixed geometry/ion owners, ordered supplied profile outputs,
and an explicit process RNG association. `transition` restores the actual INIT
owner snapshot into a runtime context and executes the native GRN reinitializer;
it never calls the old cold initializer. Runtime object identity checks refer
to that hydrated owner before and after this conditional boundary.

The source sequence refreshes environment diffusion and tissue Dm, performs the
unconditional static K draw, reinitializes the retained core/molecules and
reconstructs configured channels at carried pre-bootstrap voltage. Source
mechanical entry writes, density defaults, event finalization, conductivity and
storage clearing follow. CaATP and NaK rate caches survive. SIM starts a new
clock and journal, then uses the existing event/material/GRN/noise/mechanics/field
sequence with actual NaK. The private CaATP guard admits the retained cache at
SIM index zero; no shared composition or lifecycle source is patched.

`advance`, `run_window`, `pause` and `resume` preserve the new SIM calendar and
the complete original INIT artifact. A separately typed `FailedInitPrefix`
requires the actual retained INIT exception and accepted parent or setup
declaration. Failed, paused and capped INIT prefixes cannot enter the normal
transition. A None channel configuration that retains latent old gates is
captured and refused; an empty list reconstructs an empty enabled dictionary.

The handoff supplies selector outputs, core/world diffusion seams and the
mechanical DEC view. It does not run native profile selection, init_core,
seed/load/pickle, a whole native phase, storage or display. Native RNG streams
are process globals rather than pickle-owned data. The declaration must supply
a SIM process stream or the actual post-INIT stream with no intervening unowned
draws. N0/N1 headless INIT completion gives no native persistence credit: the
native finalizer writes pickle before accessing its last sampled report, which
can then fail with no samples.

The native checks are conditional: one reinitializes incoming saved owners; the
other starts from actual post-clear, pre-bootstrap buffers and carries three SIM
calls. Neither is an independently carried complete INIT/SIM trajectory. Every
positive case proposes fresh Decimal 100/160 phase, bootstrap and per-call
forms, original sampling eligibility and full selected state comparisons.
Existing component budgets are reused. No reference, fixture or model has been
evaluated, and pytest has not been collected.

The prospective inventory is 42 checks: 16 positive cases, five prefix refusals,
18 dependency controls and three observer failures. It contains 48 positive SIM
calls plus three reached observer calls, 928 fresh forms and 33 conditional
native captures. All are unrun. The metadata-only driver prints a plan and
otherwise refuses; it cannot launch or release a scientific round. Chief owns
independent review and any separately requested release controller.

The inherited voltage domains remain unchanged. Catalog05's no_CaATP case has
82 passed, one Nav1p2 reference refusal and 11 unrun; second-call +0.162 to
+0.380 V exceeds [-0.120,+0.060] V while native finishes three calls. That is a
reference refusal, not a tolerance failure. KLeak/CaLeak also retain inherited
guards before their constant branches. No fixture tuning or oracle widening
was used. The old signed_environment 39/40 failure remains failed. No existing
scientific pass is transferred into this feature.

Static evidence and prospective IDs live beside this note in the worker's own
workfiles. The initial source-boundary audit predates the narrow INIT02 repair;
the implementation package explicitly pins sealed INIT02 and preserves that
historical audit. Root's reference-CLI and finalizer proposals remain separate.
