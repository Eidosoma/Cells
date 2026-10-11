# R0 closeout and R1-S0 reference-only scoping (D130)

Close the independently reviewed 1 ms recording/window milestone, then prepare
the 10 ms pump–leak numerical extension. Do not edit frozen D119–D129 sources.

`relax_job.py check OUTPUT --tests XML` runs a source-bound short suite, including
two separate-process 10 ms reference smokes, corruption/coverage guards and R0
authentication. These smokes are not the complete six-control reference study.

`relax_job.py closeout OUTPUT --software SOFTWARE_COMPLETION` authenticates the
full completed D129 review and prerequisites, records the closeout, measured
recorder context and remaining junction/biological readiness gaps. No integration.

`relax_job.py launch OUTPUT --closeout CLOSEOUT_COMPLETION` launches exactly one
detached reference-only study: six unchanged seven-cell preparations, three
unchanged adaptive settings each (DOP853 base/tight and Radau), 10 ms, 1,601 saved
samples per solve. Preserve scalar equations, tolerances, 30,000 RHS-call and
4,096 accepted-step caps. Change only horizon and prospective observation/restart
times. No Cells/JAX or native BETSE simulation is run.

Check cross-solver agreement, all saved sample/accepted-endpoint domains and
accounting, and the 161-sample overlap with original 1 ms references. Store endpoint
net ion/voltage rates descriptively, not as an equilibrium verdict. Domain checks
do not mathematically enclose every instant between samples. This is producer
reference qualification pending a separate review, not full 10 ms correspondence.

The controller authenticates sources, runtime, closeout and prerequisites before
and after, seals all outputs, and preserves failure artifacts. CPUs 0–3, one BLAS
thread; 300 s worker / 600 s controller; 4 GiB worker address space; 8 MiB per new
file / 128 MiB total / 1 GiB free reserve. No polling, automatic retry or next job.

Later gates: independent saved-reference review; an explicitly scoped native
time-step/resource probe; ordinary Cells windows/restarts and the full matched
matrix. Native energy tolerance remains 1e-7 pJ. No biology, GPU, steady-state,
whole-native bounded-memory or full BETSE-parity claim follows here.
