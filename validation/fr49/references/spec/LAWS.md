# FR-49: the laws (read these, not code)

These are the equations the code-blind references implement for FR-49's registered protocol,
`fr49-compartment-compositions-v1`. Every declared value is in `cases.json`. Do not read engine code
(`src/cells/`), the engine's tests or any engine output. The equations below are complete.

## 1. Conventions

- **Units:**
  - amounts in fmol, volumes in pL, concentrations in mM (1 fmol/pL = 1 mM), time in s;
  - first-order rates in 1/s, production in fmol/s;
  - a route's conductance a in pL/s, so a × c is in fmol/s;
  - association rates in 1/(mM s), dissociation rates in 1/s.
- **Counts.** A site population declares its copies N, a count of molecules, and its sites per copy
  ν, an integer. Its capacity is S = α ν N / N_f fmol, with:
  - α the accessible fraction (dimensionless);
  - N_f = 602,214,076 sites per fmol, exact by the 2019 SI.
- **Well mixed.** Every node is well mixed, and every volume is fixed.

## 2. World L: a labelled pulse into a compartment

**The physical system.** There are two nodes, the owner cell O (volume V_O) and its compartment C
(volume V_C). A neutral species S has amounts n_O and n_C:

    J = a (n_O/V_O − n_C/V_C)          the passive route across C's bounding patch, O to C (fmol/s)
    dn_O/dt = P − J                     P: production in O, constant (fmol/s)
    dn_C/dt = J − k_d n_C               k_d: first-order clearance in C (1/s)

**No other process moves S.** In particular, the owner's other processes (it also makes other
species) never touch S, and nothing moves S across any other surface.

**The labels.** Each molecule carries one label, which never changes it physically.
- **Production** during the pulse [t₁, t₂) makes label x. At every other time it makes the base
  label.
- **Transport** moves each label in proportion to its share at the node the material leaves. The
  route is linear in each end, so x moves O → C at a x_O/V_O and C → O at a x_C/V_C.
- **Clearance** removes each label in proportion to its share.

So the labelled amounts x_O and x_C obey the same equations with their own source term:

    dx_O/dt = P_x(t) − a (x_O/V_O − x_C/V_C),    P_x = P inside [t₁, t₂), 0 outside
    dx_C/dt = a (x_O/V_O − x_C/V_C) − k_d x_C
    x_O(0) = x_C(0) = 0

and the base amounts are n − x. A node's share of x is x/n.

**The solution** is exact, by matrix exponentials. The system is linear with a piecewise-constant
source, so augment the state with the constant 1 and exponentiate on each interval between t = 0,
t₁, t₂ and the sample times.

## 3. World B: ligand binding in a compartment, with depletion

**The system.** C holds a neutral ligand L at free concentration c = n_L/V_C. A population of finite,
identical, single-occupancy sites, of capacity S (fmol), faces C:

    J_b = k_on c R − k_off B           (fmol/s, the binding rate)
    dB/dt = J_b,    dn_L/dt = −J_b,    R = S − B
    K_d = k_off / k_on                 (mM)

- **Binding is the only process that moves L in C.** The ligand total L_T = n_L + B (fmol) is
  constant.
- **The equilibrium:** with b = V_C K_d + S − L_T and d = sqrt(b² + 4 V_C L_T K_d),

      c* = 2 L_T K_d / (b + d)      for b ≥ 0,      c* = (d − b) / (2 V_C)      for b < 0,
      B* = L_T − V_C c*.

- **The transient**, exact (a Riccati equation with constant coefficients):

      dB/dt = (k_on / V_C) (B − B₁)(B − B₂),
      B₁ < B₂ the roots of B² − (L_T + S + V_C K_d) B + L_T S = 0,

  with B₁ = B*. From B(0) = B₀ < B₁,

      (B − B₁)/(B − B₂) = ((B₀ − B₁)/(B₀ − B₂)) exp(−λ t),    λ = k_on (B₂ − B₁)/V_C.

- **The node-owned variant** has the same equations. It differs only in who owns the sites, which no
  equation reads.
- **The well beside it.** World B also holds a well, a finite node elsewhere, which is washed at a
  declared time. The wash changes only the well's contents, so C's equations above hold through it
  unchanged.

## 4. Part C1: labels at a washed well, beside a compartment

**The system.** A well W (volume V_W) holds a neutral species S with no route across its surface.
Each label starts with its declared amount: x_W(0) labelled x and b_W(0) at the base.

**The wash** at t_w removes a fraction f of the well's liquid and adds the same volume of buffer at
c_buf, which carries the base label:

    x_W(t_w+) = (1 − f) x_W(t_w−)
    b_W(t_w+) = (1 − f) b_W(t_w−) + f V_W c_buf

Between washes the well's amounts are constant.

**The compartment in the same world** follows World L's equations of §2, unaffected by the wash.

## 5. Part C2: two ligands sharing one site pool in a compartment

**The system.** Ligands L₁ and L₂ in C (volume V_C) compete for one population of sites of capacity
S. Each has its own k_on,j and k_off,j:

    R = S − B₁ − B₂,    c_j = (L_T,j − B_j)/V_C
    dB_j/dt = k_on,j c_j R − k_off,j B_j        (j = 1, 2)

Binding is the only process that moves either ligand.

**The equilibrium** is the positive root (c₁, c₂) of

    V_C c_j + S (c_j/K_j) / (1 + c₁/K₁ + c₂/K₂) = L_T,j,    K_j = k_off,j / k_on,j.

**The transient** is the integral of the two equations above, from B_j(0) = 0.
