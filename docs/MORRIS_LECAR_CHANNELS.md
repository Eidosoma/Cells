# Pinned Morris–Lecar channel family

This component covers thirteen actual classes in BETSE v1.5.0
`vg_morrislecar.py`, commit `5269a714aa2593ed2a6708c4516289977d8ae1a2`.
The chemistry network imports the module, selects it for class `ML`, constructs
the configured class, initializes it and calls its run loop. The source family
has real call sites. The standalone evidence does not execute a full chemical
network or coupled tissue simulation.

| Source class | Code | State | Main distinction |
| --- | ---: | --- | --- |
| Kv_ML1 | 40 | m | +12/17-mV target; Phi=.066 |
| Kv2p1_ML | 41 | m | +14/30-mV target; Phi=.066 |
| Kv1p3_ML | 42 | m | −14/20-mV target; Phi=.066 |
| Kv1p5_ML | 43 | m | −6/15-mV target; Phi=.066 |
| Kv1p5S_ML | 44 | m | Same target, literal Phi=.00066*2 |
| Nav_ML | 45 | none | Instantaneous Na opening |
| Cav_L_ML | 46 | none | Instantaneous Ca opening, 24-mV width |
| Cav_L_ML2 | 47 | none | Instantaneous Ca opening, 12-mV width |
| Cav_N_ML | 48 | none | Instantaneous Ca opening |
| Cav_T_ML | 49 | none | Instantaneous Ca opening |
| Kir_ML | 50 | none | Source sech rather than a sigmoid |
| HCN2_ML | 51 | none | Source increasing sign, K/Na=1/.2 |
| HCN4_ML | 52 | none | Source increasing sign, wider target |

Complete law IDs are listed in the [protocol](../validation/channels/morris_lecar_channels_protocol.json)
and `MORRIS_LECAR_LAWS`. The versioned shared compositions are
`resolved_tissue@11`, `resolved_calcium@10` and `resolved_calcium_energy@4`.
Their catalog offers **53 laws**; the supplied integration fixtures exercise
**60 populations**. Complete model state retains **19/34/38 fields**,
respectively. The five ML populations with dynamics have m only; the other
eight are stateless, with absent packed slots exactly zero. Earlier model
identities retain their definitions.

The [shared integration contract](TISSUE_RETURN_CURRENT.md#morris-lecar-channels-with-the-shared-catalog)
describes those compositions. Their qualification status belongs in
[PROGRESS](../PROGRESS.md), separately from this standalone gate receipt.
No source temperature, calcium or ligand input appears in these equations.
The mixed-tissue temperature of 298.15 K does not refit their kinetics.

## Five actual clocks, eight instantaneous openings

Except for Kir, source targets are `.5*(1+tanh((V_mV-midpoint)/slope))`.
Kir is `sech((V_mV+135)/37)`. All openings read m, without a second h gate
or an inferred activation power. The source HCN2/4 targets increase with V;
their signs are preserved, without changing them to conventional hyperpolarized
activation. Their relative permeabilities are **K=1, Na=.2**, without calcium.
Other K, Na and Ca classes declare only their respective ion with weight one.

For the five dynamic K classes:

```text
raw_tau = sech((V_mV-midpoint)/(2*slope))
tau_s = raw_tau/(1000*Phi)
continuous: dm/dt = (m_inf-m)/tau_s
native: m_next = (m+dt_seconds*1000*Phi*m_inf/raw_tau)
                 /(1+dt_seconds*1000*Phi/raw_tau)
```

The native inherited update is backward Euler. Continuous relaxation and
finite-step source updates remain separately tested. The source comment calls
Phi a time constant, but its actual position in the updater makes it a
rate prefactor. Four classes use .066 and the slow Kv1p5S class uses the literal
`.00066*2=.00132`, making its effective tau exactly 50 times the fast Kv1p5 law.
Peak effective taus are 1/66 and 1/1.32 seconds. No source clock is rescaled.

The other eight classes set `kinetic_gate=False`. Every native run replaces m
with m_inf, including **dt=0**. Their `_mTau=1` and Phi=1 fields are unused by
this branch. They do **not** define a one-millisecond relaxation law. Some
source prose mentions persistent/inactivating channels; no h dynamics or
inactivation process is inferred from those descriptions.

## Hybrid array and domain contract

`kinetics(V,codes)` returns m_inf and effective tau in seconds, each with
`[...,population]` axes. Returned tau **zero** marks an absent algebraic or
padding clock. It is not a physical zero-time kinetic state.

`initial_state(V,codes)` returns the equilibrium m for dynamic classes and
zero for all absent packed slots. `opening(state,V,codes)` reads dynamic m
or the instantaneous voltage target. `rhs` advances only the five dynamic
states; its algebraic and padding entries are exactly zero. A harmless
denominator is used only for absent clocks, without flooring any real tau.

`STATE_COUNTS` declares one state for codes40--44 and zero for codes45--52.
State, V and codes share `[...,population]` axes with independent leading
worlds. There is no synthetic h axis. The final population count is declared
by the code array. An integrating model can represent absent state as `[]`;
its uniformly packed representation must keep those slots exactly zero.
Native objects still store an m attribute as an algebraic readout, which is
distinct from an ODE/checkpoint state in this component.

`PAD_CODE=-1` is neutral padding; shared code zero retains its earlier meaning
and is invalid here. Padding has V=state=target=tau=opening=RHS=0. The
computational voltage range is −0.120 through +0.060 V, and dynamic m is finite
in [0,1]. All absent state must be exactly zero. `domain_valid` rejects unknown
or noninteger codes, booleans, malformed axes and invalid raw declarations,
including values discarded by empty broadcasting. Kernels require validation
before physical use. No physical trial is clipped or repaired.

Availability controls belong outside the opening, as in the source chemistry
run loop's `P*relative_permeability*maxDm*moddy`. Closing conductance does not
invent a different gate clock. Each mixed-ion HCN population shares one
opening/control across its K and Na routes. Nominal source reversal voltages
are recorded as metadata rather than imposed on ionic electrochemistry.

## Source evidence and meaningful duration

The independent [80-digit reference](../validation/channels/morris_lecar_channels_reference.py)
uses scalar millivolt equations and imports no Cells, NumPy or JAX helper.
Actual native AST captures bind the class file, inherited updater, metadata,
network call sites and configuration. `vg_morrislecar.py` SHA-256 is
`90e9d4dd2ea93bb3c292649aa31a330914ac897cae07094e0b070167bb4383f0`.
All upstream copies live in external evidence.

The five dynamic clamps depolarize from −80 to 0 mV and recover at −80 mV.
Each phase spans twelve **effective** taus. Native backward-Euler traces refine
at 2/4/8 subdivisions of an independent geometric clock; continuous RK4 cases
use 32/64/128 steps over twelve taus. The slow law retains its full multi-second
duration. Eight algebraic laws instead receive direct voltage steps at dt0,
ordinary dt and a deliberately large dt; no settling clock is introduced.

Source configuration comments mention `Kv_ML2`, but no such concrete class
exists. The raw lookup failure is saved separately from the thirteen working
classes and is not turned into an invented alias. Targeted source captures
also preserve reordered, empty and duplicate assignment scatter.

Host checks select `tests/unit/test_morris_lecar_channels.py -k 'not jax'`.
Two CPU JAX prototypes select `-k jax` only after the meaningful host/native
receipt passes, under the Chief's explicit conditional authorization. The new
worker wrapper reuses the established guard and frozen helper functions;
prior runners and delivered component files are unchanged. Receipts and any
failures are linked from the worker's [log](../agent-work/cells-worker-01/WORK_LOG.md).
The component receipt covers standalone gates and clocks. Coupled model
histories, complete checkpoints and GPU checks have their own recorded
qualification; they do not inherit it from these component tests.
