# Isolated regulatory reference: M1b

Implemented as Cells 0.2.0 on 2026-09-08. This is an independently expressed JAX
implementation of the isolated miR200/Zeb/ZEB equations identified in BITSEY,
not the whole bioelectric simulator or a reproduction of the cancer paper tables.
See the [acceptance report](../reports/M1B_ACCEPTANCE.md) for measured comparisons.

## Source and reuse boundary

The reference is Joel Grodstein's
[BITSEY repository](https://gitlab.com/grodstein/bitsey), fixed at commit
`b2cb370aaecbc8299f259bc4251d5396c81f19a6`. The relevant implementation is
[GRN_miRNA.py at that revision](https://gitlab.com/grodstein/bitsey/-/blob/b2cb370aaecbc8299f259bc4251d5396c81f19a6/cancer_GJ_sims/GRN_miRNA.py).
The existing exploration's `STARTING_POINT.md` and `SMOKE_RESULTS.md` identify
the two smallest source cases. Their external research-tree location is recorded
in [Scientific basis](SCIENTIFIC_BASIS.md#betse-and-bitsey-as-complementary-references).

The previous exploration checkout was absent. A separate, clean, pinned checkout
was obtained under Cells' ignored `upstream/bitsey/`. No existing research lane
or upstream source was modified. Both native source helpers ran in the separate
environment pinned by [requirements-reference.txt](../requirements-reference.txt).
Cells itself does not import that checkout or require Matplotlib.

The pinned Git tree contains no license/licence/copying-named file. In particular,
sim_toolbox.py refers to a LICENSE that is not present in that tree. Public
availability is not recorded as permission to redistribute its implementation.
No upstream implementation is vendored into Cells; only our equation expression,
provenance, and generated numerical fixtures are added. Reuse terms remain open
before any future upstream code vendoring or redistribution. This inspection is
not a legal clearance, and the unresolved paper-table mapping remains separate.

## Exact model boundary

Only three evolving coordinates are primary numerical state:

| Cells coordinate | Upstream name | Role |
| --- | --- | --- |
| mir200_total | miR200_total | Total miR200 regulatory coordinate |
| zeb_mrna_total | Zeb_mRNA_total | Total Zeb mRNA regulatory coordinate |
| zeb_protein | ZEB_prot | ZEB protein regulatory coordinate |

Snail is a fixed, explicit model parameter, set to 72 in both reference cases.
The source's normal, non-iterative mode is retained: ITERATE=False and no
MIR200_TGT forcing. A change to that approximation requires a different model
identity, not a silent numerical correction. The parameter-set identifier is
`bitsey-b2cb370-mirna-simple`; the Cells model identifier is `emt_mirna@1`.

There are no contacts in these cases. In the source, these regulatory species
have zero membrane permeability, their regulatory slopes ignore voltage, and
Snail does not evolve. The isolated regulatory subsystem therefore closes on
these three variables. The source comparison checks that its isolated full
simulator returns the same regulatory derivatives as its regulatory gate at
36 boundary/seeded points. This justifies this isolated reduction only; it does
not justify removing ionic dynamics when voltage-dependent contact is introduced.

The Cells regulatory layout contains active flags and stable IDs, without a
fictional physical volume. There is one active cell; unused capacity stays zero.
No ions, membrane voltage, junctions, energy budget, growth, or lineage are
simulated by this model. Its restart is complete for these equations, not a
complete BITSEY cell-state packet or a biological inheritance boundary.

## Coordinates, equations, and algebraic refresh

Coordinates are labelled `bitsey_scaled_coordinate`, and time is
`bitsey_time_unit`. The source scales Snail, miR200, Zeb mRNA, and ZEB protein
by 2500, 250, 30, and 18000 respectively. Its regulatory comments describe rates
per hour while the simulator describes its clock as seconds; M1b does not resolve
or silently convert that physical-time correspondence. These numbers must not be
treated as calibrated fmol, tissue concentrations, or seconds.

Write u = miR200 total, m = Zeb mRNA total, z = ZEB protein, and s = fixed Snail.
For H(v; K, n, L) = (1 + L(v/K)^n) / (1 + (v/K)^n), the scaled equations are:

```text
du/dt = 6 H(s; 72, 2, 0.4) H(z; 100/9, 3, 0.1) - 0.05 u
dm/dt = (5/12) H(s; 72, 2, 10) H(z; 25/9, 2, 15) - 0.5 m
dz/dt = (1/6) sum[i=0..6] choose(6,i) L_i Y_i - 0.1 z

Y_i = m (u/40)^i / (1 + u/40)^6
L_i = [1, 0.5, 0.2, 0.02, 0.02, 0.02, 0.02]
```

Each Y_i is a per-configuration complex; its binomial multiplicity is separate.
Thus sum choose(6,i) Y_i = m. Our equivalent expression uses p=u/(40+u) and
q=40/(40+u), then Y_i=m p^i q^(6-i), avoiding unnecessarily large powers.
The weighted translation coefficients are [1, 3, 3, 0.4, 0.3, 0.12, 0.02].

The source's simple algorithm uses total miRNA in the binding equation, sets its
free-miRNA proxy equal to that total, and restores the primary total after its
temporary calculation. Cells reproduces this approximation explicitly. It does
not replace it with a free-miRNA mass-balance solve. The mRNA partition identity
is an algebraic check, not a claim of conserved total molecular mass: transcription,
translation and degradation are open reduced-model processes, and the source's
miRNA approximation is not a physically complete binding budget.

Complexes are recomputed at every RK stage from the primary state. Observations
first interpolate accepted primary states and then recompute complexes; they do
not independently interpolate stale derived variables. The source-style label
is M when m > u+2, E when u > m+2, and X otherwise. It is an observer convention
in scaled coordinates, not a diagnosis, an extra state variable, or evidence
of commitment, memory robustness, heredity, or organ function.

## Numerical contract and reference cases

Both examples use Snail 72, horizon 10000, CPU float64, and RK4 step 0.1:

| Definition | Initial (u, m, z) | Comparison |
| --- | --- | --- |
| [E-like start](../configs/emt_isolated_e.json) | (100, 0, 0) | Source instantiate(); sim_me(72, 100, 0, 0) |
| [M-like start](../configs/emt_isolated_m.json) | (0, 100, 100) | Source instantiate(); sim_me(72, 0, 100, 100) |

Only source.kind=none is supported for this isolated reference. Fixed Snail is
still supplied model context, not an evolved regulatory variable. Branching may
extend the horizon or change observation times but may not change that parameter,
initial state, model, or solver. Future interventions need their own contract.

The implementation caps the largest actual RK4 step at 0.25. This is a conservative
supported step domain, not an adaptive error estimate or a convergence guarantee
for every allowed nonnegative initial state/Snail value. Quantitative acceptance
is demonstrated for the two shipped cases and derivative probes. Non-finite or
negative accepted states and failed algebraic checks are refused without clipping.
Resource limits cover the bounded full trace; streaming is not yet implemented.

The independent CPU references use SciPy Radau and BDF with rtol=1e-11 and
atol=1e-12. Their [documented solver definitions](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html)
provide two integration-method comparisons; the test oracle uses a separate
NumPy polynomial expression, never the Cells RHS. RK4 refinement at 0.2, 0.1,
and 0.05 tests transient accuracy, not just settled labels. This choice does not
select a numerical method or step for the future coupled bioelectric model.

The native source helpers retain their original adaptive explicit Euler settings
(base step 0.005, relative concentration-change bound 0.001, voltage-change bound
0.0001). We compare against their actual sample times. A read-only return-frame
observer captures the source's live accepted time separately from its final saved
sample; neither is relabelled as exactly 10000. Cells ends exactly at 10000.

## Reproduce the reference capture

For a new checkout, these commands obtain only the pinned scientific source and
its reference environment. Do not run them over an existing source directory:

```bash
git clone --filter=blob:none --no-checkout --depth 1 https://gitlab.com/grodstein/bitsey.git upstream/bitsey
git -C upstream/bitsey fetch --depth 1 origin b2cb370aaecbc8299f259bc4251d5396c81f19a6
git -C upstream/bitsey sparse-checkout set --cone cancer_GJ_sims
git -C upstream/bitsey switch --detach b2cb370aaecbc8299f259bc4251d5396c81f19a6
python3 -m venv .reference-venv
.reference-venv/bin/python -m pip install -r requirements-reference.txt
taskset -c 0-3 .reference-venv/bin/python scripts/capture_emt_reference.py upstream/bitsey --output runs/new-emt-source
taskset -c 0-3 .venv/bin/python scripts/verify_emt_build.py runs/new-emt-source/reference.json --output runs/new-emt-verification
```

Use CPU affinity appropriate to your host. Capture uses three fresh subprocesses,
each bounded to 120 seconds; it launches no tumour network or parameter sweep.
The checkout must be clean before and after. Generated numerical derivative
fixtures are retained in [tests/fixtures](../tests/fixtures/emt_source_probes.json),
so ordinary regression tests do not require the upstream checkout or network.
Full logs, source snapshots, and Cells run arrays remain ignored local artifacts.

## Next gate

M1c-a's [passive contact](PASSIVE_CONTACT.md) now verifies two cells and analytic
reciprocal exchange, including unequal volumes, blocked contacts, release, and
restart. CORE-003 now verifies [local reaction/transport composition](REACTION_TRANSPORT.md)
on an independent amount model; it does not calibrate or connect EMT coordinates.
D018's [one-cell physical engineering model](BIOELECTRIC_CELL_SPEC.md) now has
a qualified [independent numerical reference](BIOELECTRIC_NUMERICS.md) and
verified [production JAX implementation](BIOELECTRIC_CELL.md) in 0.5.0.
D021 specifies a [physical gated pair](SELECTIVE_CONTACT_SPEC.md), subsequently
qualified and implemented through D022/D023 in 0.6.0.
The [source-coupling map](SOURCE_COUPLING_MAP.md) now verifies instantaneous
source functions and identifies their different gating, transport and charge
approximations.
D024/SPEC-003 now pins the [complete source-compatible pair](SOURCE_EMT_PAIR_SPEC.md),
its nominal-unit/state/control contract, prepared full packets and native full-RHS
probes. D025/NUM-004 subsequently qualifies the bounded coupled trajectories;
D026/MODEL-005 implements the [nominal pair](SOURCE_EMT_PAIR.md) in 0.7.0 against
those frozen references. Longer switching and memory/relay protocols remain
separate gates; the source reuse boundary is unchanged. Do not call
the linear transport fixture the source's gap-junction mechanism, or use this
isolated reduction to imply coupled validation. Its nominal source-time units
are not silently interchangeable with the passive fixture's seconds.
