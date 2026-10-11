# REF-004b: empty-biomolecule configuration correction

D090, 2026-09-14. This is a configuration-only successor to
[D089's setup/single-transfer preflight](BETSE_CHANNEL_TRANSPORT_PREFLIGHT.md).
The original capture, sources, numeric protocol, tests and handoff remain frozen.

## Observed failure and narrow correction

The user-reviewed attempt at
`runs/ref-004b-transport-2026-09-14/capture-01` stopped after **4.672 seconds**.
It completed the three network-off cases, then failed while initializing the
empty general network. BETSE's runtime wrapper rejected `config_substances=None`
at `MasterOfNetworks.tissue_init`: its annotation requires a sequence or array.
The old adapter emitted `general network: biomolecules: null`.

That was our configuration mismatch, not an ion-transport rejection, timeout
or memory limit. No channel-runner or Cells comparison ran. The original 76
software tests passed but did not check this actual native setup type contract.
The failure is retained as a failure, not retroactively qualified.

Change only `general network / biomolecules` from `null` to `[]`. Do not turn
other optional network entries into empty lists indiscriminately: native
reaction/transporter/channel/modulator presence checks distinguish null from
an enabled list. No auxiliary substance, charge repair or native code patch is
introduced. The network-off configuration also carries the empty list, although
the disabled network does not consume it.

Source: pinned v1.5.0
[network initialization](../upstream/betse-v1.5.0/betse/science/chemistry/networks.py:306)
and [molecule configuration dispatch](../upstream/betse-v1.5.0/betse/science/chemistry/molecules.py:137).
The annotation rejects null before entering the method, despite its internal
null check. We leave that upstream behavior unchanged.

## Reuse and tests

The [amendment](../validation/betse/channel_transport_setup_fix/amendment.json)
pins the failed registration and original numerical protocol. Keep every
equation, tolerance, case, initial state, temperature, timestep and resource
bound unchanged. Import the frozen Cells worker and numerical checker directly.
A versioned native worker retains the original native worker body except for
the configuration-provider call; an AST comparison enforces that one-call
difference. This avoids runtime monkeypatching of either adapter or BETSE.

The new regression checks the actual isolated BETSE YAML loader, then applies
BETSE's type-checking library to the actual `tissue_init` parameter annotation.
For all four configurations, loaded null must be rejected and loaded `[]`
accepted. Source bytes, package lock, YAML bytes and loaded temperature/clocks
are checked. This is a **parameter-loading/type-contract test**, not a claim
that a world or network was initialized. Full native initialization is exercised
by the fresh numerical preflight, with real phase/simulator/channel objects.

The contract probe is a short subprocess with a 20-second ceiling. Its logs,
eight YAML inputs and JSON result are retained alongside the focused-test XML.
Run the unchanged 76 original tests together with correction tests for the
configuration-only delta, frozen native-body equivalence, unchanged Cells/checker,
failure preservation, strict membership and failure/no-retry handling.

## Evidence and execution boundary

A separate preservation receipt records all **22 files** of the failed attempt,
the original 63 source-capsule entries, 393 earlier source hashes and historical
reports. It authenticates the already accepted 352 files / 51 production modules
and the earlier isolated-channel closeout without rerunning any audit or model.
Do not use the old job's growing-directory membership guard on new source files;
check the frozen inventories themselves and register new sources separately.

One explicitly user-approved fresh capture re-executes the twelve original
cases, including the three previously completed network-off controls. No old
partial output is counted as new execution. The new registration binds the
amendment, source capsule, preservation receipt, passing software XML and actual
native configuration/type-contract packet before numerical workers launch.

Limits remain CPU 0–3, float64, 120 seconds per numerical worker, 300 seconds
total, 128 MiB aggregate artifacts and 32 MiB per file. File ceilings are not RAM
limits. Keep partial output, logs and any rejection. Launch detached and return;
no polling, automatic retry, audit or full-loop pilot follows.

An eventual pass is still `capture_pass_pending_audit`. No coupled trajectory,
biological calibration, general BETSE parity or GPU qualification is claimed.
