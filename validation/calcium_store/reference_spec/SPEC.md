# Calcium store: what the independent references must compute

**Written 25 November 2026 by the store worlds' builder, before any reference exists.** The references are written by
someone who has read nothing but this folder: this document and `inputs.json`. It holds equations, parameters, initial
states, observables, times and the accuracy wanted. It holds no output of any run. The numbers of the world are
synthetic and its own.

**Rules for the references' author.** Read this folder only. Do not read the engine (`src/cells/`), its tests, its
design notes or any run output. Import nothing from `cells`. NumPy, SciPy, mpmath and the standard library are fine.
Where something here is unclear, ask the lead; do not settle it from the code. State what you read and what you assumed.

## 1. Conventions

- **Units.** Amounts n in fmol, volumes V in pL, concentrations c = n/V in mM (fmol per pL), areas A in m², permeabilities
  P in m/s, voltages in V, capacitances in F, currents in A, energies in pJ, times in s, temperatures in K.
- **Constants.** The exact SI values (`inputs.json`, `constants`): F = N_A e, R = N_A k_B. RT is in J/mol. A charge of
  one fmol of unit valence is 1e-15 F coulomb. A rate in fmol/s times an energy in J/mol is 1e-3 pJ/s.
- **B(x) = x / (e^x - 1),** with B(0) = 1.
- **A patch** has an inside node i and an outside node o. Its voltage is V = phi_i - phi_o. Both patches here have the
  cell inside, so the store patch's voltage is V_b = phi_cell - phi_store.
- **A cycle's ends** are N and P; V_NP = phi_N - phi_P and psi = F V_NP / (RT). Its affinity x is its free energy over RT,
  negative when the forward cycle runs down. J = k a S (1 - e^x) in fmol of cycles per second, with k the capacity (fmol/s)
  and a the availability in [0, 1] (1 in the world).
- **ln** is the natural logarithm. c0 = 1 mM is the standard concentration of every activity and potential here.

## 2. The laws

### 2.1 Constant-field flux (patches, calcium leaks, release, channel)

For a species of valence z on a patch, area A, permeability P, opening m in [0, 1], x = z F V/(RT):

    J = 1e15 A P m [c_i B(-x) - c_o B(x)]          fmol/s, positive from the inside to the outside
    heat rate = 1e-3 J [RT ln(c_i/c_o) + z F V]    pJ/s, >= 0

The inside loses J, the outside gains J.

### 2.2 The release's opening

    m = f_IP3 x f_Ca,     each f the factor of one condition, evaluated with the present concentrations at the condition's node
    for a condition with reads j (species s_j, half saturation K_j in mM, coefficient n_j):
    z_j = n_j (ln c_sj - ln K_j);   ln h_j = -ln(1 + e^(-z_j)) for activation,  -ln(1 + e^(z_j)) for inhibition
    f = exp( sum_j ln h_j )

The release is the constant-field flux of calcium on the bounding patch with this m. Its direction follows from 2.1.
(Reported as "release", positive from the store into the cell: minus J of 2.1.)

### 2.3 The calcium channel (gates m and h)

Constant-field flux of calcium on the plasma patch with opening a_0 m^2 h, a_0 its abundance and P its maximal
permeability. With u = V - 0.010 V:

    m_inf = 1/(1 + exp(-(u + 0.030)/0.006))        h_inf = 1/(1 + exp((u + 0.080)/0.0064))
    tau_m = 0.005 + 0.020/(1 + exp((u + 0.025)/0.005)) s
    tau_h = 0.020 + 0.050/(1 + exp((u + 0.040)/0.007)) s
    dm/dt = (m_inf - m)/tau_m        dh/dt = (h_inf - h)/tau_h

V is the plasma patch's voltage. Heat as 2.1.

### 2.4 The ATP-driven transporter (both pumps)

N is the side it pumps from, P the side it fills; it moves n ions of one species of valence z per cycle; ATP, ADP and Pi
are read at N and do not change. mu are standard potentials over RT at c0.

    x_fuel = mu_ADP + mu_Pi - mu_ATP + ln( (ADP/c0)(Pi/c0) / (ATP/c0) )
    x = x_fuel + n ln(c_P/c_N) - n z psi
    S = [1 + (K/c_N)^n]^-1 [1 + K_ATP/ATP]^-1
    J = k a S (1 - e^x);      one-way forward J+ = k a S
    N loses n J, P gains n J (per second);   current from N to P = 1e-15 F n z J ampere
    heat rate = -1e-3 RT J x  pJ/s (>= 0);   work rate supplied by the fuel = -1e-3 RT J x_fuel  pJ/s

### 2.5 The exchanger (3 Na : 1 Ca)

N is the cell, P the outside. J > 0 moves 3 Na from P to N and 1 Ca from N to P per cycle. With a = Na_N/K_Na,
b = Na_P/K_Na, c = Ca_N/K_Ca, d = Ca_P/K_Ca, and u = F V_NP/(RT):

    D = (1 + a^3 + b^3)(1 + c + d)
    J = k a_v [ b^3 c e^(-u/2) - a^3 d e^(u/2) ] / D          (a_v the availability)
    x = 3 ln(Na_N/Na_P) + ln(Ca_P/Ca_N) + u;   J = k a_v S (1 - e^x) with S = b^3 c e^(-u/2)/D
    heat rate = -1e-3 RT J x;   no work

### 2.6 The symports

One inward cycle moves nu_s of each species s from P to N (N is the cell in the states of section 5). It moves no net
charge. With e^x = prod_s (c_N,s / c_P,s)^nu_s:

    J = k a (1 - e^x)/(1 + e^x) = k a tanh(-x/2);   x = sum_s nu_s ln(c_N,s/c_P,s)
    N gains nu_s J of s, P loses it;   J+ + J- = k a;   heat rate = -1e-3 RT J x;   no voltage in it

### 2.7 The buffers

At each site (the cell and the store), with activities a_s = n_s/(V c0) and standard potentials mu_s (over RT):

    r = V c0 k [ prod_reactants a  -  exp(mu_products - mu_reactants) prod_products a ]        fmol/s, V the site's volume
    bind_first:  Ca + B -> CaB;     bind_second:  Ca + CaB -> Ca2B

each with its own k (`forward_rate_per_s`). r > 0 consumes reactants and makes products. Heat rate =
1e-3 RT r [ sum ln a_reactants - sum ln a_products - (mu_products - mu_reactants) ] >= 0; no work.

### 2.8 Charge and voltage

Each node has a fixed charge X_v (fmol of unit charge), constant, so that the charges at t = 0 give the declared initial
voltages. With q_v = 1e-15 F ( sum_s z_s n_s,v + X_v ):

    q_store = C_b (phi_store - phi_cell)                       so V_b = -q_store/C_b
    q_cell + q_store = C_m (phi_cell - phi_outside)            so V_m = (q_cell + q_store)/C_m
    q_outside = -(q_cell + q_store)                            (the world is closed; phi_outside = 0)

Every charge-carrying mover above changes the q of its two nodes through the amounts; nothing else does.

## 3. The world (`inputs.json`, `store_world`)

One cell, one store, one finite outside node, closed: no bath, no face, no junction. Every mover:

| Mover | Patch | Law | Species |
| --- | --- | --- | --- |
| the plasma patch's own permeability | plasma | 2.1 | Na, K, Cl |
| the bounding patch's own permeability | bounding | 2.1 | K, Cl |
| `plasma_leak`, `store_leak`, `release` | plasma, bounding, bounding | 2.1 (release with 2.2) | Ca |
| `calcium_channel` | plasma | 2.3 | Ca |
| `plasma_pump` | plasma: N cell, P outside | 2.4 | Ca (z = 2), n as listed |
| `store_pump` | bounding: N cell, P store | 2.4 | Ca (z = 2), n as listed |
| `exchanger` | plasma: N cell, P outside | 2.5 | Na, Ca |
| `bind_first`, `bind_second` | cell and store | 2.7 | Ca, B, CaB, Ca2B |

- The rows listed under a node are the species present there. A species not listed at a node does not exist there for
  the references.
- `constant_rows`: ATP, ADP, Pi and IP3 in the cell do not change (nothing moves them); Na in the store has no mover.
  IP3 (valence -3) and the fuel rows (valence 0) enter only through the conditions, the pumps and the fixed charges.
- B, CaB and Ca2B cross no patch.
- All movers act together at every instant. The references integrate the ordinary differential equations exactly (to the
  accuracy below), with no splitting.
- **Variants:** `store_world` (everything) and `store_world_without_buffers` (the two reactions do not run; every other
  number is the same).

**Observables, at each time of `times_s`,** for each variant:
1. every row's amount at every node (fmol); V_m and V_b (V); m and h;
2. each mover's cumulative transfer since t = 0 (fmol): for 2.1 movers, per species, positive from the inside (cell) to
   the outside, and the release positive from the store into the cell; each pump's and the exchanger's cycles (fmol,
   forward positive); each reaction's extent at each site (fmol);
3. each mover's cumulative heat and each pump's cumulative work since t = 0 (pJ);
4. the capacitor energy 1e12 (C_m V_m^2/2 + C_b V_b^2/2) pJ, and the total free energy
   G = sum over nodes and rows of 1e-3 RT n [ ln(c/c0) - 1 + mu_s ] + capacitor energy (mu_s from `standard_mu_RT` and
   `fuel_potentials_RT`, 0 for every other species). Check for yourself that G + heat - work is constant.

**At t = 0** also: every mover's rate (fmol/s, or cycles) and heat rate, the two conditions' factors, and dV_m/dt, dV_b/dt.

**The material block,** at t = 0 and at the last time, each variant: hold the potentials and the gates at their present
values. Let y = (Ca cell, Ca store, Ca outside, Na cell, Na outside) be the amounts, and g(y) the rate of change of y
(fmol/s) from these movers only: `plasma_leak`, `store_leak`, `release` (its factors moving with Ca cell), the channel,
both pumps, the exchanger. Not the patches' own permeabilities, not the buffers. Return the 5 x 5 Jacobian dg/dy (1/s),
its eigenvalues, and the largest modulus, (a) as stated and (b) with the release's opening held at its present value.

**Controls** (`controls`): the same observables for the world with each single change listed. They are the power of the
comparison, not part of it: a comparison band must be smaller than what each change moves.

## 4. Accuracy

- The world's amounts, voltages and gates: 1e-10 relative to the largest change of that observable over the run (state
  the achieved error per observable). Use at least two different integrators (for example an explicit high-order one
  with a stiff one), with a tolerance study, and show that they agree to that.
- Cumulative transfers, heats and work: 1e-9 relative to the largest of their own kind (a quadrature in the same
  integration is fine).
- The kernel states of section 5: 1e-13 relative, in 40 or more digits of working precision, rounded once to a double.
- Give the fastest rates of the system you find (1/s) and the error of each method. The engine's comparison is at second
  order in its own step (0.2 ms and below), so references at 1e-9 are far below it.

## 5. Kernel states for rows 8 and 9 (`pump_states`, `exchanger_states`, `symport_states`)

**For every pump state** (2.4) return: x, x_fuel, S, J+, J, heat rate, work rate, the current N to P (A); dJ/dV_NP (fmol/s
per V) at fixed concentrations; dJ/dn at N and at P (1/s, n = c V with the state's volumes); the two end moves; in_domain
= (abs(x) <= 80). For z not 0 also V_stall, the V_NP at which x = 0, and J at V_stall - 1e-6, V_stall and V_stall + 1e-6 V.

**For every exchanger state** (2.5): x, S, J, heat rate, dJ/dV_NP, dJ/dn for each of the four rows (Na N, Na P, Ca N, Ca P),
V_rev (the V_NP with x = 0) and J at V_rev - 1e-6, V_rev, V_rev + 1e-6; the current N to P, which is -1e-15 F J (each
forward cycle carries one unit of charge from P to N); in_domain = (x <= 80).

**For every symport state** (2.6): x, J, heat rate, dJ/dn at each of the two ends of each species, the moves at each end, the
sum of the one-way rates; J with V_NP changed (it must not change); in_domain = (x <= 80).

**Edge states asked for, and present in the files:** valences 2, 1, -1 and 0 with n = 1 to 4; cycles reversed by the fuel, by the
gradient and by the voltage; an x near 70; a role far below and far above its K; ATP almost absent; K very small and very large;
availability 0 and 1e-10; capacity 0; equal concentrations at zero and nonzero voltage (the exchanger's reversal is then at
zero voltage only); a saturating outside sodium; calcium absent on one side; a symport at exactly equal concentrations, near
equilibrium (0.1%), and far from it both ways, with the voltage changed alone. States tagged "beyond the domain" are for the
engine's refusal; return their values too, with in_domain false.

## 6. What to write, and where

Into `validation/calcium_store/references/` (new), and nowhere else:
- `README.md`: what was read, the method, the achieved errors, every assumption and every question;
- `forms.py` (2.1 to 2.7), `world.py` (section 3), and `api.py` with: `store_world(variant, control=None)`,
  `initial_rates(variant)`, `material_block(variant, time)`, `pump_states()`, `exchanger_states()`, `symport_states()`;
- `values.json`: every output on the inputs, as plain numbers, so that a test reads numbers and runs no integrator;
  a `--check` mode of the writing script regenerates it and compares.
Each output names its unit. No file there imports `cells`.
