# SPEC-006: first state-bearing channel reference

2026-09-09, D049 / R010. **The design/reference checks pass.** Production remains
Cells 0.11.0; no new channel model is registered in the JAX engine. The complete
two-context regression matrix passes all 2670 tests, including 105 new tests.

The [contract](../docs/VOLTAGE_GATED_CHANNEL_SPEC.md) specifies one K-bound,
Kv1.5-style channel with separate activation `m`, inactivation `h`, abundance,
permeability, membrane geometry and experimental availability. Both gates are
primary state; the present open fraction `m h` is only a readout. A constant-field
channel route adds to, rather than replacing or sharing controls with, baseline
leak and pump routes.

## Source and evidence boundary

We reviewed the `Kv1p5` rate expressions, `VgKABC` voltage conversion and gate
product, the gate updater, and license at the same pinned BETSE v1.5.0 commit
used by the [capability roadmap](../docs/BETSE_CAPABILITY_ROADMAP.md).
The [channel source](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/channels/vg_k.py)
and [updater](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/channels/channelsabc.py)
are pinned by commit and byte hashes in the panel. They were read, not installed,
vendored or executed. Continuous-rate agreement is a different claim from
native BETSE time-stepping agreement or feature parity.

The source's cited [Philipson et al. 1991 abstract](https://pubmed.ncbi.nlm.nih.gov/1986382/)
supports a qualitative heterologous-expression/current/inactivation lead. No
experimental trace, uncertainty model or coefficient-level provenance was
recovered here. The assembly's 298.15 K setting, synthetic 1e-8 m/s permeability
and unit abundance are engineering inputs, not physiological calibration.

## Frozen arithmetic and gate-response checks

[voltage_gated_channel_v1.json](../configs/reference/voltage_gated_channel_v1.json)
was written and hashed before evaluation. Both embedded ionic assemblies equal
the unchanged SPEC-005 fixtures exactly. A new immutable scalar reference uses
seconds/volts and stable sigmoid/exponential arithmetic; its independent
70-digit Decimal comparator uses native millisecond/millivolt expressions and
a direct constant-field numerator. Neither imports the production engine.

The [saved receipt](spec-006-design-check.json) reports **7,528 checks, zero
failures**. The largest normalized comparison error is about 0.00404 of its frozen
arithmetic budget, well below one. These are deterministic arithmetic limits,
not statistical uncertainty or a coupled numerical-method qualification.

| Check family | Evidence |
| --- | --- |
| Gate rates and units | 52 equilibrium/time-constant comparisons over 13 voltages; 182 derivative comparisons and 182 inward-boundary checks |
| Analytic relaxation | 2,548 gate-value comparisons and 2,548 monotonicity checks over both time scales, seven states and seven elapsed-time factors |
| Zero duration and composition | 182 exact no-op checks; 182 held-voltage semigroup comparisons |
| Prescribed-voltage protocols | Seven protocols / 62 saved rows: activation, inactivation, recovery, block/release, 0.1 ms pulse, and two equal-open-fraction histories |
| Event/readout semantics | Independent Decimal prefix replay, right-continuous voltage/control readouts, sampling independence, gates continuing during availability block, and three final-time no-duration checks |
| Coupled instantaneous rates | 84 independent channel flux comparisons, 84 ionic-energy and 84 charge-rate checks; material/bath/binding checks for every declared species |
| Mechanism separation | Off/zero-parameter reductions, independent abundance/permeability/area scaling, Nernst/zero-voltage limits and 30 exact species permutations |
| History sufficiency | Equal current open fraction and ionic response do not imply equal gate derivatives or future response under a common voltage input |

The reference carries no coupled-cell trajectory or new production checkpoint.
The protocol rows are analytic **isolated-gate** responses to prescribed input.
The physical reference evaluates instantaneous feedback rates only. A future
production implementation must retain separate channel transfer history in
addition to both gate states and existing charge/exchange/energy anchors.

## What this taught us about the next build

Within the deliberately bounded -120 to +60 mV engineering domain, activation
time constants span **1.352–22.286 ms**, while inactivation spans **0.690–3.480 s**.
This is already a two-timescale problem inside one channel, before adding tissue.
It motivates retaining both states and qualifying any future multirate reduction.

At the fastest declared gate, the old multispecies 10 ms step gives a held-gate
RK4 linear amplification factor of **78.2216**, exceeding the stability limit
of one. This is an algebraic counterexample, not a newly run candidate trajectory.
No new method or timestep is selected. Exact exponential evolution at a held
voltage is also not exact for a feedback-coupled voltage that changes during a
step. NUM-007 must qualify the coupled system before CORE-007 production work.

Availability zero suppresses channel current, not gate evolution. Neither gate
is inferred from current voltage on initialization or restart. Prescribed gate
voltage is not an electrode model. Ionic/capacitor energy checks explicitly omit
gating charge, conformational energy and channel turnover; no thermodynamic
claim about the full protein is made.

## Verification and preservation

All **105 new tests pass in 1.33 s**, with warnings treated as errors; see the
[test receipt](spec-006-tests-01.xml). Tests include strict definitions/JSON,
nonfinite/domain refusals, nonliteral species names, explicit initial gates,
history accounting, retained disabled state, event/sampling rules, independent
reference imports and non-overwriting receipt output. No numerical test failed
and no frozen tolerance or input was retuned. A style-only lambda correction
was made before the first test/evidence run.

The [full two-context regression matrix](spec-006-regression-01/verification.json)
passes **2670 tests**, with zero failures, errors or skips:

| Test context | Passed | Test-context time |
| --- | --- | --- |
| Current production / new reference | 1699 | 553.188 s |
| Preserved historical reference | 971 | 157.658 s |
| Total | 2670 | 710.846 s |

These times are summed test-suite times, not simulator throughput measurements.
Ruff lint and formatting checks pass across all 183 Python files. The final
[preservation receipt](spec-006-closeout.json) records 369 pre-existing files:
358 remain byte-identical and 11 have intentional documentation-only changes.
The accepted CORE-006 source identity is checked directly by the design script;
all 41 production
modules and the package/dependency files are unchanged. Old reference code,
datasets, numerical gates, acceptance artifacts and the closed descriptive pilot
are preserved. The separate [CORE-006 saved-evidence audit passes again](spec-006-core006-audit.json):
773 payloads, 43 scalar outputs/four cohorts and exact saved restart/branch
comparisons, with no numerical solver run by that audit.

## Reproduce

Use new output paths; existing receipts are never overwritten:

```bash
.venv/bin/python scripts/check_voltage_gated_channel.py --output reports/my-spec006-check.json
.venv/bin/python -m pytest -q -W error tests/unit/test_voltage_gated_channel_reference.py
.venv/bin/python scripts/test_cells_build.py --output reports/my-spec006-regression
```

The checker is offline and uses the retained CORE-006 release receipt to verify
unchanged production. The full matrix additionally needs the preserved historical
source archives and reference artifacts. Sources and all seven gate-response
tables are included by identity or value in the saved design receipt.

| Object | SHA-256 |
| --- | --- |
| Frozen SPEC-006 panel | `16b6e245ba2cef921fc48e1a4c7f8ebd03481724e7de5d1062fcf0d8fdeed09c` |
| Physical/gate contract | `a66fb7027ece28a25d380f67f8c673f61f9e40b6aca3541ced2c5ebfe34deecd` |
| Design-check receipt | `4446d68fd8ef7096deed17952f014ba0536c3f28be8e591932d606ff5d07b13c` |
| Unchanged CORE-006 release | `ec084d0f626fbb3793714bbb7ea346688d1f1244078869507396a57aec1f5005` |

Next: register a bounded NUM-007 coupled-cell panel, including deliberately
nonequilibrium gate/ionic states, independent references/refinement, stage and
interior gate/amount/voltage domains, controls and complete material/energy
histories. Select a candidate method only from that evidence. Production channel
support, channel catalogs, physical ionic graphs, finite baths, GPU execution,
organs and the deferred E02 campaign remain later work.
