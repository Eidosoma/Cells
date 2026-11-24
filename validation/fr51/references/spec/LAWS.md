# FR-51: the laws (read these, not code)

These are the equations the code-blind references implement. Every declared value is in
`cases.json`. Do not read engine code (`src/cells/`), the engine's tests or any engine output. The
equations below are complete; no other document is needed.

## 1. Constants and conventions

- **Constants**, exact by the 2019 SI:
  - F = 6.02214076e23 × 1.602176634e-19 C/mol;
  - R = 6.02214076e23 × 1.380649e-23 J/(mol K);
  - N_A = 6.02214076e23 /mol.
- **Temperature:** T is declared per case, in K.
- **Units:** amounts in fmol, concentrations in mM (1 mM = 1 mol/m³ = 1 fmol/pL), areas in m²,
  permeabilities in m/s, voltages in V, fluxes in fmol/s, currents in A.
- **The patch voltage** is V = φ_in − φ_out: the cell's potential minus the outside node's.
- **Signs:**
  - a flux J is **outward-positive**: positive J moves the ion from the cell to the outside;
  - a current is **outward-positive**: I = 10⁻¹⁵ F z J, the charge carried outward (A), z the ion's
    valence.

## 2. The unblocked population: constant-field (GHK) permeation

A channel population on a patch of area A carries each permeant ion s, of valence z_s, with:

    J_s = 1e15 × A × P × r_s × a × o × v × (c_i,s B(−x_s) − c_o,s B(x_s))      (fmol/s, outward)
    x_s = z_s F V / (R T)
    B(x) = x / (e^x − 1),  with B(0) = 1 (the limit).

- **P** is the population's maximal permeability (m/s), and r_s the ion's relative permeability
  (dimensionless; 1 for every population here).
- **a** is the population's **abundance**, a dimensionless relative abundance (a count is not
  declared, except in case C2, §6).
- **o** is the law's open fraction and **v** the availability, both dimensionless in [0, 1]. Every
  population here is gate-free and fully available: o = v = 1.
- **c_i** and **c_o** are the ion's concentrations (mM) in the cell and at the outside node.
- The factor 1e15 converts mol/s to fmol/s.

**Two properties to report, which the criteria use:**
- At equal concentrations c_i = c_o = c, J = 1e15 A P r a o v c x, so I is linear in V through 0:
  I = A P r a o v c z² F² V / (R T).
- At unequal concentrations, J reverses at the Nernst potential, E_s = (R T/(z_s F)) ln(c_o,s/c_i,s).

**The slope**, used by §5:

    dJ_s/dV = 1e15 A P r_s a o v (z_s F/(R T)) (−c_i,s B′(−x_s) − c_o,s B′(x_s)),
    B′(x) = (e^x − 1 − x e^x) / (e^x − 1)²,  B′(0) = −1/2.

## 3. The block: weighted modes of reversible open-channel block

**The idea.** A blocker of valence z_B binds in the open pore from one side, and the binding's
voltage dependence follows Woodhull's model (Woodhull 1973, J. Gen. Physiol. 61:687–708; PMID
4541078). The population's channels sit in M blocking modes with fractions w_k, each with its own
dissociation constant at zero voltage, K_k(0), and its own steepness. The block is instantaneous
(at equilibrium at every voltage), and it multiplies every permeant ion's flux by the same
unblocked fraction u.

**The declared values** (per population, `cases.json`):
- **the blocker:** its valence z_B (a nonzero integer), its side (`outside` or `inside`), and its
  concentration c_B (mM, ≥ 0), a constant;
- **the voltage reference:** `membrane_voltage`, giving V_ref = V; or `reversal_of` an ion,
  giving V_ref = V − E_ion, the Nernst potential of §2 for that ion at the case's concentrations;
- **the modes**, each with:
  - a weight w_k in [0, 1], the weights summing to 1;
  - K_k(0) in mM, > 0;
  - exactly one of:
    - `electrical_distance` δ_k in [0, 1], whose steepness is m_k = |z_B| δ_k;
    - `effective_valence` z_eff,k > 0, whose steepness is m_k = z_eff,k. It may exceed |z_B|, for
      block whose voltage dependence comes partly from permeant ions moving with the blocker.

**The law, per mode k:**

    s = +1 for a blocker from the outside, −1 for one from the inside
    a_k = s × sgn(z_B) × m_k × F / (R T)                       (1/V)
    K_k = K_k(0) × exp(a_k V_ref)                               (mM)
    θ_k = c_B / (c_B + K_k)                                     the blocked fraction of mode k
    1 − θ_k = K_k / (c_B + K_k)                                 the unblocked fraction of mode k

For the electrical-distance form, a_k = s z_B δ_k F/(R T). So a cation entering from the outside
binds more tightly as V falls (block relieved by depolarisation), and a cation entering from the
inside binds more tightly as V rises (inward rectification).

**The population's unblocked fraction:**

    u = ( Σ_k w_k (1 − θ_k) ) / ( Σ_k w_k )

The blocked flux of each permeant ion is J_s,blocked = u × J_s of §2.

**Exact values the reference must reproduce** (the criteria test both ends):
- At c_B = 0, every θ_k = 0, so u = 1 exactly.
- At strong block, u is small, and must be computed with relative accuracy. For one mode with
  c_B/K = 1e18, u = 1/(1 + 1e18) ≈ 1e-18. The difference 1 − Σ w θ cannot represent this in
  binary64, so use the form above, or higher precision (§7).

**Indications, not claims.** These are for orientation only. Each rests on one study, and none
enters the criteria:
- A population's polyamine-induced rectification shifts in proportion to the shift in E_K
  (Lopatin and Nichols 1996, J. Gen. Physiol. 108:105–113; PMID 8854340). This is the motive for
  the reversal reference.
- The apparent valence of spermine block of an inward-rectifier K⁺ channel is about 5, greater
  than spermine's charge of 4, and arises mainly from K⁺ ions (Shin and Lu 2005, J. Gen. Physiol.
  125:413–426; PMID 15795311). This is the motive for the effective-valence form.
- A two-population description of an inward rectifier's block appears in Yan and Ishihara 2005 (J.
  Physiol. 563:725–744; PMID 15618275).

## 4. Derivatives of the fraction

    d(1 − θ_k)/dV_ref = a_k θ_k (1 − θ_k)
    du/dV_ref = ( Σ_k w_k a_k θ_k (1 − θ_k) ) / ( Σ_k w_k )

Compute θ_k (1 − θ_k) as the product of the two fractions above, each formed directly.

## 5. The blocked population's slopes

**The voltage slope** of the blocked current, at fixed concentrations. E does not depend on V, so
dV_ref/dV = 1:

    dI_blocked/dV = 1e-15 F Σ_s z_s ( u dJ_s/dV + J_s du/dV_ref )          (S = A/V)

**The concentration slopes** of the blocked flux, at fixed V. Under the reversal reference, u reads
the concentrations through E_ion: ∂V_ref/∂c_o = −R T/(z_ion F c_o) and
∂V_ref/∂c_i = +R T/(z_ion F c_i). Under the membrane-voltage reference both are 0. For the ion
s = ion:

    ∂J_s,blocked/∂c_o = u × (−1e15 A P r_s a o v B(x_s)) + J_s × du/dV_ref × ∂V_ref/∂c_o
    ∂J_s,blocked/∂c_i = u × (+1e15 A P r_s a o v B(−x_s)) + J_s × du/dV_ref × ∂V_ref/∂c_i

These are in fmol/s per mM.

## 6. One count

**C1, abundance.** Multiplying a by any factor multiplies every flux by it, blocked or not, and
leaves u unchanged.

**C2, units.** Here the population is declared as a count of units:
- N = a × A × ρ_ref units (molecules), with a reference density ρ_ref in units/m²;
- the abundance read by §2 is a = N / (A ρ_ref).

Doubling N doubles every flux and leaves u unchanged.

## 7. Accuracy

Evaluate every quantity to at least 30 significant digits. For example, use Python's `decimal`
module with a 50-digit context: it has `exp` and `ln`, and B(x) can be summed from its series near
0. Report each value as a decimal string with at least 20 significant digits.

The strong-block and near-reversal points are where binary64 loses accuracy. Those are the reason
for the requirement.
