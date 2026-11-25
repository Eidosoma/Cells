# The laws: closed forms

Every input is in `inputs.json`. Work in the standard library's `decimal` at 60 digits or more, and
read each declared number as the exact value of its nearest double. Nothing here comes from engine
code.

## 0. Conventions

- **Concentration** c = n/V, in mM (1 mM = 1 fmol/pL). RT = R·T/1000 pJ/fmol, with R = N_A k_B,
  N_A = 6.02214076 × 10²³ mol⁻¹, k_B = 1.380649 × 10⁻²³ J/K, and T the world's temperature.
- **Free energy** of n fmol of one species in V pL: F(n, V) = RT n (ln(n/V) − 1), with c in units of
  1 mM and F(0, ·) = 0. Per pL of liquid: f(c) = RT c (ln c − 1). The −1 is needed: without it the
  identities of §5 do not close. Standard potentials cancel, since every amount that enters is booked.
- **φ(r) = r ln r − r + 1,** with φ(0) = 1. It is never negative, and φ(1) = 0.
- **A heat** is the free energy lost, in pJ, so it is never negative. Free energies and heats sum over
  the world's species.
- **u = 2⁻⁵³,** binary64's unit roundoff. ε = 2u.
- **A holder** is an inlet, a node or a collector. A collector starts at zero volume.

## 1. Two wells joined by a passive face

For one neutral species, permeance PA (pL/s) between volumes V₁ and V₂, starting at n₁ and n₂:

    dn₁/dt = −PA (n₁/V₁ − n₂/V₂) = −dn₂/dt
    k  = PA (1/V₁ + 1/V₂)                 M∞ = (c₁ − c₂) / (1/V₁ + 1/V₂)
    m*(t) = M∞ (1 − e^(−kt))              n₁(t) = n₁ − m*(t),   n₂(t) = n₂ + m*(t)

**The free energy lost** when m fmol have crossed from 1 to 2:

    D(m) = F(n₁, V₁) + F(n₂, V₂) − F(n₁ − m, V₁) − F(n₂ + m, V₂),   dD/dm = A = RT ln(c₁/c₂) at the current levels

The face's heat to time t is D(m*(t)). With an event between, it is the sum over the intervals on
either side.

## 2. The scheme's one-step map (a published scheme, not engine code)

The scheme declared for arms 1, 2 and 6 is the second-order ARS(2,2,2) of Ascher, Ruuth and Spiteri
(1997). A passive neutral transfer moves by its explicit stages alone:

    γ = 1 − 1/√2,  δ = 1 − 1/(2γ)
    Y₁ = y,   Y₂ = y + γ h g(Y₁),   y⁺ = y + h [δ g(Y₁) + (1 − δ) g(Y₂)]

- **On the two wells** one step of h leaves the difference c₁ − c₂ multiplied by R(z) = 1 − z + z²/2,
  z = kh, since (1 − δ)γ = 1/2. So it moves m_R(h) = M∞ (1 − R(z)) = M∞ (z − z²/2).
- **Against the exact solution:** by Taylor's theorem with Lagrange's remainder,
  0 ≤ R(z) − e^(−z) ≤ z³/6, so 0 ≤ m*(h) − m_R(h) ≤ M∞ z³/6. To leading order the gap falls by 8 per
  halving.
- **For a linear system** y′ = B y the same stages give y⁺ = (I + hB + (hB)²/2) y.

**Placeholder L1: the default heat's declared law.** A one-step value H_def(h) at a declared start, in
closed form on the stages above, and a bound B_def(h) ≥ |H_def(h) − D(m_R(h))| from its Taylor
remainder. Until it is filled, CRITERIA.md §3.4's ladder judges T4.

## 3. An exchange at a well

Fraction f of a well's liquid (n fmol in V pL, c = n/V) leaves as a sample, and the same volume of
buffer at x enters:

    sample = f n        supplied = f V x        n′ = (1 − f) n + f V x,   c′ = n′/V
    H_ev = RT [ (1 − f) n ln(c/c′) + f V x ln(x/c′) ] = RT V c′ [ (1 − f) φ(c/c′) + f φ(x/c′) ]

- **The withdrawal loses nothing** (the sample has the well's composition). H_ev is the refill's mixing
  heat. A sum over species is implied.
- **Small f:** H_ev = RT V [ f c φ(x/c) − f² (x − c)²/(2c) + O(f³) ]. With fV = QΔt, the first term is
  §5's rate times Δt.

## 4. Flow through well-mixed holders

Node i has a fixed volume V_i. A link j → i carries Q_ij pL/s of j's liquid. Inlets hold declared
concentrations x_I, and at every node the inflow equals the outflow. For one species:

    dn_i/dt = Σ_{j→i} Q_ij c_j − (Σ_{i→l} Q_li) c_i,   c_j = n_j/V_j or x_I
    dn_K/dt = Σ_{j→K} Q_Kj c_j,   dV_K/dt = Σ_{j→K} Q_Kj,   supplied(t) = ∫ Σ_{I→i} Q_iI x_I dt

**The decimal propagator.** Put x_I (as a constant row), the n_i and n_K in one vector y, so y′ = G y
with constant G between switches. Then y(t) = e^(Gt) y(0).
- Compute e^(Gt) by scaling and squaring: halve t until the matrix norm is at most 2⁻⁸, sum the Taylor
  series until a term is below 10⁻⁵⁸ of the sum, and square back, carrying at least 20 digits more
  than are published.
- **Equal rates need no special case here.** The closed forms below are the independent check.

**A chain I → A → B → K,** with a = Q/V_A, b = Q/V_B, u_A = n_A(0) − V_A x and u_B = n_B(0) − V_B x:

    E(t) = (e^(−at) − e^(−bt))/(b − a),   and  E(t) = t e^(−at)  when a = b   (the confluent form)
    n_A(t) = V_A x + u_A e^(−at)
    n_B(t) = V_B x + u_B e^(−bt) + a u_A E(t)
    n_K(t) = n_A(0) + n_B(0) + Q x t − n_A(t) − n_B(t)

- **m equal chambers in series,** all tracer in the first at t = 0 and clean inflow:
  n_j(t) = n_1(0) (at)^(j−1) e^(−at)/(j − 1)!, j = 1 … m.

## 5. The heat of flow

**The total to time t** is a state function:

    H_tot(t) = Σ_i [F(n_i(0), V_i) − F(n_i(t), V_i)] + ∫ Σ_{I→i} Q_iI f(x_I) dt − F(n_K(t), V_K(t))

**Each holder's share,** for a node or collector at concentration y with inflows Q_l at x_l:

    r(t) = RT Σ_l Q_l [ x_l ln(x_l/y) − x_l + y ] = RT Σ_l Q_l y φ(x_l/y),   H_holder(t) = ∫₀ᵗ r dt

- For a node: dF/dt = Σ_l Q_l f(x_l) − (Σ_l Q_l) f(y) − r. For a collector: dF/dt = Σ_l Q_l f(x_l) − r.
- **Σ over holders of H_holder(t) = H_tot(t),** exactly. This is the check on the integrals.
- At t = 0 an empty collector's y is the first inflow's concentration, so its r starts at 0.
- With B starting at a trace ε, r_B starts at RT Q [x ln(x/ε) − x + ε] and falls logarithmically from
  times of order εV_B/(Q x) on: an integrable singularity as ε → 0.

## 6. The growing collector, by portions

A portion (v, x) joins a collector holding (n, V):  n′ = n + v x,  V′ = V + v,  y = n′/V′, and

    loss = RT [ n ln(c/y) + v x ln(x/y) ] = RT V y φ(c/y) + RT v y φ(x/y),   c = n/V

The first term of the second form is the resident's part and the second the arriving portion's. Into
zero volume both are zero: the first portion loses exactly nothing. The total after several portions
does not depend on their order, and the per-portion losses do.

## 7. Labels

A label on a species is an amount that moves with it. For each label the amounts obey §4's equations
with that label's own start. Liquid from an inlet belongs to the base label. The labels of a holder sum
to its species. A collector's labelled contents are what reached it, by label.

## 8. Flow beside a face

With a face of permeance PA between A and B beside §4's links, y′ = (G_Q + G_P) y, where G_P holds
only the face's terms ∓PA/V. Use the propagator of G_Q + G_P.
- **The face's heat rate** is PA (c_A − c_B) RT ln(c_A/c_B), and its integral is H_face(t).
- **The total** H_tot(t) of §5 (a state function) equals Σ H_holder(t) + H_face(t).
- **At Q = 0** this is §1 with V_A and V_B.

## 9. Rounding counts

**The model of arithmetic.** Each rounded operation on a term of size at most s errs by at most u·s. A
quantity that passes through at most m rounded operations a step, for S steps, from a declared start,
is off by at most

    e_round = m (S + 1) u s          (the + 1 covers the declared start and the final read)

**The counts m,** on the longest path from one stored level to the next. H is the number of holders in
the world's network (inlets and collector included), and N its number of species.

| Count | Formula | Why |
| --- | --- | --- |
| m_n, flow | 2 (H + 18) | Two half-steps. In each: an H-term sum of products (H roundings), the propagator's entries (8 ε = 16 u each, absolute, with ‖P‖ ≤ 1; declared, re-measured, pending), and the store (increment and level, 2) |
| m_f, a face step | 40 | Two stages at 15 each (level read 1, division 1, the flux's evaluation 8, permeance conversion 4, product 1), the stage update (4), and the final combination and store (6) |
| m_q, a label | 6H + 106 | Two half-steps. In each: a share's numerator (H + 17), its denominator (H + 16), their quotient (1), the amount it multiplies (H + 18), and the product (1) |
| m_h, a mixing heat | 24 + 2H (N + 1) | Two half-steps. In each: one portion's term (12: two divisions, ratio, logarithm 2, φ 3, products 3, accumulation 1) and the sum over portions, species and holders (H (N + 1)) |
| m_V, a volume | m_n | Moved as an amount |

An event costs no more than 8 roundings, so it never adds to a path longer than a step's. An inlet or
portion's amount is a product or two, inside the same counts.

**The scales s.**
- **An amount or label:** the species' total amount in the world to that time, start plus supplied (N_x).
- **A volume:** the collector's volume at the end.
- **A heat:** s_F = RT (Λ + 1) Σ_x N_x, with Λ the largest |ln(c/1 mM)| over every concentration the world
  declares (start levels, inlets, buffers). The levels stay inside that range, so Λ needs no run.

## 10. Step-error models, for sizing plants only

They are used only to size plants before a run. No honest tolerance reads them.
- **p = 1,** a holder's heat at step h: (h/2)·TV(r), with TV the total variation of r over the run. A
  one-sided booking of ∫ r dt errs by this.
- **p = 2,** arm 6's amounts: the published Strang map y⁺ = P(h/2) E(h) P(h/2) y, with P the exact
  propagator of G_Q and E(h) = I + hG_P + (hG_P)²/2. Run it in decimal at the three registered steps and
  form CRITERIA.md's estimate.

## 11. The planted series

| Plant | The planted quantity |
| --- | --- |
| P1 | F2's reference read as F1's, and the reverse |
| P2 | No mixing in B: n_A as honest, n_B(t) = n_B(0), n_K(t) = n_A(0) + Q x t − n_A(t) |
| P3 | First-order transfer at k = Q/V_A for both chambers, no volume moved: the chain of §4 with b replaced by a (x as honest), and V_K = 0. At equal volumes its amounts are the honest ones |
| P4 | U's amounts with every Q of U's row multiplied by 1 + 2⁻²⁰; T's unchanged |
| P5 | H_holder plus RT ∫ Σ_l Q_l (x_l − y) dt |
| P7 | H_B(T) = Σ_steps h r_B at each step's start, at the finest step |
| P9 | The collector starts as a node of 2⁻¹⁰ pL at 10⁻¹² mM: the first portion's loss by §6 with that resident |
| P10 | The honest rows at time 2t read at time t |
| P11 | A collector's portion booked at the outlet node's share, not its origin's: at each half-step, tag arriving at K = (Σ_j P_Kj n_j) × (tag_B/n_B at the half-step's start), and the nodes' tags as honest |
| P14 | k from V₁ alone: the step moves M∞ (1 − R(h PA/V₁)) |
| P15 | A transfer that depends on the background: g = PA ((c₁ + c₂)/2) ln(c₁/c₂), one step by §2's stages |
| P16 | The heat with its weight at the step's start: m A(0), with m the run's own transfer |
| P17 | The exchange applied after the step: the sample is f × the no-event twin's amount one step later |
| P19 | Arm 6's amounts by the Lie split P(h) then E(h) |

P6, P8, P12, P13 and P18 need no planted series.
