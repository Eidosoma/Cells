# FR-43 part 3: the references' spec (the same-draws integration)

This is the spec for an independent, code-blind reference of FR-43 part 3. It covers C3.4 and
D315's two-way case.

**What is being modelled.** A low-count population of integer units sits in a membrane patch. Its
active units move a neutral species S between a cell and its finite outside node. The rate at which
units assemble reads S's current concentration.

**What the reference gives.** For each world, the time and channel of every event, and the pools
at it. It uses the declared values and random draws given here. Cells' engine results are compared
with it afterwards. This folder holds declared values and protocol only, so no engine value is in it.

**The files:**
- `part3.json`: the worlds, the laws and conventions, and the requested outputs, with their units;
- `draws.json`: each world's draws, (u1_k, u2_k) for k = 0 … 255, as `float.hex` strings;
- `make_draws.py`: the standalone generator of `draws.json`, from the rule below. It imports JAX's
  random primitives and nothing of the engine.

## The process

**The two kinds of state:**
- the continuous state x is the amounts of S in the cell and the node (fmol), at fixed volumes (pL);
- the integer state N = (n_free, n_active) is the counts of the site's unit states.

Between events, N is constant and x follows the ODEs of `part3.json` (`system`).

**The transfer** is passive and linear: J = G (n_cell/V_cell − n_node/V_node), in fmol/s from the
cell to the node, with G = g · n_active pL/s.

**W3 adds an existing writer.** It produces S in the cell at a constant rate and clears it at first
order at the node.

## The event rule

The rule is a random time change, the hybrid next-reaction method.

1. **Propensities.** a_j = k_j · Π_k ff(n_k, r_jk) · φ_j, with:
   - ff(n, r) = n!/(n − r)! (ordered tuples, so the assembly 2 free → active at n_free = 2 has
     ff = 2);
   - φ_j = c/(1 mM) for a channel that declares a read (c = n/V of the read row, at the current
     state), and 1 otherwise.

   a₀ is the sum over channels, in declared order.
2. **The hazard.** H(t) is the integral of a₀ along the solution from the previous event (or from
   t = 0), and restarts at 0 after every event.
3. **Event k fires** (k = 0, 1, 2, …) at the first t with H(t) = E_k, E_k = −ln u1_k.
4. **The channel** is chosen at the crossing state:
   - c_j = a_1 + … + a_j is summed left to right in declared order;
   - the channel is the first j with c_j > min(u2_k · a₀, nextafter(a₀, 0)).
5. **The jump.** N ← N − r_j + p_j, and x is continuous across it.

The integration continues to the horizon.

## The random-draw protocol

Every draw is counter-based. It depends only on (seed, site, domain, counter), so a restart or a
batch draws the same values. The derivation is Threefry-2x32 under JAX's partitionable Threefry
(`jax_threefry_partitionable`, on by default since JAX 0.5):

    base    = jax.random.key(seed, impl="threefry2x32")            seed in [0, 2**32)
    site    = fold_in(fold_in(base, low32(s)), high32(s))           s: the site's declared index
    stream  = fold_in(site, domain)                                 domain: events 1, partition 2
    draw k  = fold_in(fold_in(stream, low32(k)), high32(k))         k: the draw's counter
    words   = jax.random.bits(draw k, shape=(count,), dtype=uint64)
    u       = ((words & (2**52 - 1)) + 0.5) * 2**-52                the open interval (0, 1)

Each `fold_in` takes one unsigned 32-bit word.

**Event k of a site** uses its events stream's draw k with count 2: (u1_k, u2_k) = (u[0], u[1]).
So a site's first event uses counter 0, whenever it occurs. The partition domain (one uniform per
unit at a division) is not needed here.

**The premise check.** Before integrating, regenerate the draws with your own code from this
written rule. Then compare them with `draws.json` bit for bit, as `float.hex`.

**The rule depends on JAX's word layout.** `jax.random.bits` under the partitionable Threefry
gives each output word from the key and the word's position. The written rule names that layout,
so a regeneration outside JAX must reproduce it, and JAX's legacy layout gives other words.
(Added after the references returned, at their author's note; nothing above changed.)

## What to produce

Produce `part3.json`'s `requested_outputs` for each world, as one JSON each:
- **events:** for every event up to the horizon, its time, its channel, the counts after it, the
  pools at it and the cumulative transferred amount, plus the turnover totals for W3;
- **samples** at the listed times. A sample that coincides with an event takes the counts after
  it (added after the references returned, at their author's note);
- **the method and its accuracy.**

The accuracy target is event times to 1e-10 s and amounts to 1e-12 relative. A suggested method is
the ODE with H appended, integrated by Radau at rtol 1e-12, with the events located by a root
finder on H − E_k. Cross-check it with a second method, such as DOP853 at the same tolerance, or a
closed form where you derive one. Then report the largest difference between the two.

The spec gives no time step and no splitting. Both belong to the engine, and its step-halving study
measures them.

## Where the results go

Put the reference's code under `validation/fr43_part3/references/`, with its own README. Put its
outputs as small JSON files under `validation/fr43_part3/references/results/`. The lead may name
another place.
