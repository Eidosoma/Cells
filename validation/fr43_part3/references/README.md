# FR-43 part 3: the code-blind references (the same-draws integration)

This folder holds an independent reference for FR-43 part 3: a low-count integer population of
units on continuous chemistry. For each of `spec/part3.json`'s four worlds it gives every event to
the horizon (time, channel, counts after, pools, cumulative transfer and, for W3, the turnover
totals) and the samples at 1 s. It uses the declared values and `spec/draws.json`'s draws.

It was written from `spec/` alone, at commit 0ab4c9d2. No engine code, run or result was read,
and nothing here imports the engine. `spec/` is unchanged from that commit.

## Files

- `spec/`: the declared values, laws, protocol and draws (not edited here).
- `stream_draws.py`: the premise check. It regenerates every draw from the written stream rule
  and compares the draws bit for bit with `spec/draws.json`, by two routes:
  - a Threefry-2x32 (20 rounds) written out with no JAX, with JAX's key words, fold_in counter
    and partitionable 64-bit bits spelled out;
  - this module's own calls to `jax.random.key`, `fold_in` and `bits`.
- `same_draws.py`: the integration. Each method assembles the model from the spec on its own.
- `results/draws_check.json`: the premise check. Both routes are identical to `draws.json` on all
  4 × 256 × 2 doubles.
- `results/<world>.json`: one per world. The top level is `{world, events, samples, method,
  accuracy}`, as `requested_outputs` names it. Separate keys hold the `diagnostics`, the
  `event_diagnostics` (each event's draws, threshold E_k, propensities at the crossing and channel
  margin), the `sample_diagnostics` (the hazard since the last event) and the `provenance`.
- `tests/unit/test_fr43_part3_references.py` (in the repository's tests): the self-check below.

## Regenerating

From the repository root, on one CPU:

    taskset -c 6 /mnt/workspaces/Cells/venv-cpu/bin/python -I \
        validation/fr43_part3/references/same_draws.py

This runs the premise check (both routes) and stops if any draw differs. It then writes
`results/`, in about 60 s. `--routes scratch` skips the JAX route, and `--worlds <id,...>`
limits the run to some worlds. Each result's `provenance` records the code's commit, any
uncommitted change to the code and the library versions.

## Method

- **The reported values (the closed form).** Between events N is constant and the pools follow
  x' = A x + p, with A = [[-a, b], [a, -(b + k)]], a = G/V_cell, b = G/V_node and
  p = (P_cell, 0).
  - x(τ) = e^{Aτ} x0 + τ φ1(Aτ) p, and ∫x = τ φ1(Aτ) x0 + τ² φ2(Aτ) p, by Sylvester's formula on
    A's two real eigenvalues (A = diag(0, -k) when no unit conducts).
  - H, the transferred, the produced and the cleared amounts are linear in ∫x.
  - It is evaluated in Python's `decimal` at 50 significant digits. Declared values and draws
    enter as their exact binary64 values.
  - Event times come from a bracketed, safeguarded Newton on H(τ) − E_k (H' = a0 > 0), stopped at
    1e-45 s.
  - The channel rule is applied in exact arithmetic at the crossing state, and again in binary64
    with the nextafter guard; the two agree at every event.
  - Values are rounded to binary64 at output.
- **The cross-check (the ODE).** The state is (n_cell, n_node, H, transferred, produced,
  cleared), with H appended and restarted at every event.
  - It is integrated by `scipy.integrate.solve_ivp`, Radau, rtol 1e-12, atol 1e-15, with the
    affine right-hand side's exact Jacobian.
  - Events are found by the terminal event function H − E_k, then refined by Newton on H at the end
    point of a re-integration from the previous event, to 1e-15 s.
  - DOP853 runs at the same tolerances, and also at rtol 1e-13.
- **The arithmetic check.** The closed form is run again at 70 digits, compared before rounding.
  It measures arithmetic only, not the derivation.

## Accuracy

Largest differences over all events and samples. The first value in each pair is event times in
s; the second is amounts, relative.

| world | events | closed form vs Radau 1e-12 | vs DOP853 1e-12 | vs DOP853 1e-13 | 50 vs 70 digits |
|---|---|---|---|---|---|
| W1_two_subunits_feedback | 27 | 3.6e-15 / 1.8e-15 | 1.7e-13 / 6.1e-14 | 1.8e-14 / 7.1e-15 | 8e-49 / 3e-49 |
| W2_four_subunits_feedback | 20 | 8.9e-15 / 6.8e-15 | 7.1e-14 / 5.4e-14 | 1.1e-14 / 6.3e-15 | 5e-49 / 3e-49 |
| W3_two_way_turnover | 24 | 7.1e-15 / 1.5e-14 | 1.4e-13 / 1.3e-13 | 1.4e-14 / 1.4e-14 | 5e-46 / 7e-46 |
| W4_four_subunits_node_read | 43 | 1.1e-14 / 1.2e-14 | 4.3e-14 / 5.7e-14 | 3.6e-15 / 6.4e-15 | 1e-45 / 1e-45 |

Every method gives the same events, channels and counts in every world. The spec's target is
1e-10 s and 1e-12 relative. Radau, the stated cross-check, meets it by nearly four orders in event times
and by 65 times or more in amounts (1.5e-14 at worst). DOP853 at rtol 1e-12 meets it by 7.7 times
in amounts, and 1e-13 brings it to the level of Radau. The largest absolute amount difference
against Radau is 8.8e-14 fmol, in W3.

**Distances from the decision boundaries.** These are the margins a comparison with a coarser
integration depends on:
- the smallest relative channel margin is 1.8e-3 in W2 (10 competing events) and 2.9e-3 in W4
  (21); W1 and W3 never have two channels open at once;
- the closest event to a sample time is 9.2e-4 s, in W4;
- the last events fall 0.98, 1.08, 0.139 and 0.169 s before the horizon, and the next ones
  4.05, 0.227, 0.383 and 0.324 s after it.

## Conventions where the spec leaves a choice

- **Declared decimals are read as binary64**, as JSON gives them. The difference from exact
  decimals is about 1e-17 relative.
- **A sample takes the counts after any event at or before its time.** No event lies within
  9.2e-4 s of a sample time, so the choice changes nothing here.
- **`transferred_fmol` is the signed integral of J from t = 0.** It is positive from the cell to
  the node.

## The self-check

`tests/unit/test_fr43_part3_references.py` recomputes the results' checks from `spec/` and
`results/` alone, with no engine import and no JAX:
- the draws through `stream_draws.py`'s Threefry, bit for bit, and Random123's known-answer
  vectors for the hash;
- per world, with the test's own assembly of the law as a 7 × 7 augmented linear system
  propagated by `scipy.linalg.expm` from each reported event:
  - the hazard reaches E_k at each reported time, to 1e-12 s;
  - the pools and totals match, to 1e-12 relative;
  - the channel rule and the jump give what is reported;
  - the accounting identities hold, to 1e-13 fmol;
  - no event is missed before the horizon;
  - the samples match;
- the stated accuracy against the target.

It takes 1.4 s as a process on one CPU (0.8 s of pytest time).
