# FR-50: the laws (read these, not code)

These are the equations the code-blind references implement for FR-50's registered protocol,
`fr50-one-way-records-v1`. Every declared value is in `cases.json`. Do not read engine code
(`src/cells/`), the engine's tests or any engine output. The equations below are complete.

## 1. Conventions

- **Constants**, exact by the 2019 SI: F = 6.02214076e23 × 1.602176634e-19 C/mol and
  R = 6.02214076e23 × 1.380649e-23 J/(mol K). T is declared per case.
- **Units:**
  - amounts in fmol, volumes in pL, concentrations in mM (1 mM = 1 mol/m³ = 1 fmol/pL), time in s;
  - areas in m², permeabilities in m/s, diffusivities in m²/s, lengths in m;
  - one-way fluxes in fmol/s, and their cumulative records in fmol;
  - a transporter's one-way rates in fmol of cycles per s, and its records in fmol of cycles.
- **The patch voltage** is V = φ_in − φ_out, and x = z F V/(R T) for an ion of valence z.
- **B(x) = x/(e^x − 1)**, with B(0) = 1.

**A one-way record** of a route is the time integral of one direction's flux. Its two directions
are forward and backward, and forward minus backward is the route's net record. Each case below
names its route's forward direction.

## 2. One-way fluxes, per route

| Route | Forward | Forward flux | Backward flux |
| --- | --- | --- | --- |
| Neutral passive route on a patch (Fick), conductance a = 1e15 P A o (pL/s) | Inward: the outside node to the cell | a c_out | a c_in |
| Constant-field route of an ion on a patch (GHK), prefactor g = 1e15 P A o (pL/s) | Inward | g c_out B(x) | g c_in B(−x) |
| @3's membrane route (a patch's own permeability) | Outward: the cell to the outside node | g c_in B(−x) | g c_out B(x) |
| A channel population, g = 1e15 P r a o v u A | Outward | g c_in B(−x) | g c_out B(x) |
| A junction route, g = 1e15 P A gate availability | Sender to receiver | g c_sender B(−x) | g c_receiver B(x) |
| An uncharged face, g = 1e15 D A / L | Sender to receiver | g c_sender | g c_receiver |

- In the channel row, u is FR-51's unblocked fraction (§4), and 1 for an unblocked population.
- In the junction row, x is formed from the sender's potential minus the receiver's.
- For a neutral species, x = 0 and B = 1.
- **Ussing's ratio** follows from these: for a charged route, backward/forward = (c_from/c_to) e^(±x),
  with the sign of the route's own direction. For a patch route, inward/outward =
  (c_out/c_in) e^(−x).

## 3. A transporter's one-way cycle rates (Hill's cycle fluxes)

The law is `atp_driven_transporter_mass_action_positive@1`. It moves n of a neutral role from the
patch's cell to its outside node per cycle, and hydrolyses one ATP to ADP + Pi at its held fuel.
The fuel is read at the cell and never moved.

    ΔG_cyc/(R T) = Δμ°/(R T) + ln(c_ADP c_Pi / (c_ATP c0)) + n ln(c_out / c_in),
    Δμ°/(R T) = μ°(ADP)/(R T) + μ°(Pi)/(R T) − μ°(ATP)/(R T)
    S = [1 + (K/c_in)^n]^(−1) [1 + K_ATP/c_ATP]^(−1)
    J₊ = k a S                 forward cycles (fmol/s)
    J₋ = J₊ exp(ΔG_cyc/(R T))  backward cycles (fmol/s)
    net cycle rate = J₊ − J₋ = k a S (1 − exp(ΔG_cyc/(R T)))

- k is the capacity in fmol of cycles per s, and a the availability.
- K and K_ATP are half-saturations in mM, and c0 is the standard concentration in mM.
- **At equilibrium** ΔG_cyc = 0, so J₊ = J₋ = k a S, and the net is 0.

## 4. FR-51's unblocked fraction (for case E4)

The block in E4 has one mode, with a reference `reversal_of` K. So V_ref = V − E_K, with
E_K = (R T/F) ln(c_o/c_i), and

    K₁ = K₁(0) exp(s z_B δ F V_ref / (R T)),    u = K₁ / (c_B + K₁).

At V = E_K, V_ref = 0, so u = K₁(0)/(c_B + K₁(0)).

## 5. The worlds' trajectories

- **Steady cases** (K1, K4, E1–E4): the declared state is steady, so every flux is constant. Each
  record at time t is its flux times t.
- **K2, a relaxing neutral route** between a cell (V_O) and a finite node (V_N). With the total
  n_tot = n_O + n_N constant and k = a (1/V_O + 1/V_N):

      c_O(t) = c̄ + (c_O(0) − c̄) e^(−k t),   c_N(t) = c̄ − (V_O/V_N)(c_O(0) − c̄) e^(−k t),
      c̄ = n_tot / (V_O + V_N).

  The records are F(t) = ∫₀ᵗ a c_N dt′ (inward) and B(t) = ∫₀ᵗ a c_O dt′ (outward), in closed form.

## 6. Accuracy

- Evaluate every quantity to at least 30 significant digits. Python's `decimal` with a 50-digit
  context has `exp` and `ln`, and B(x) can be summed from its series near 0.
- Report decimal strings of at least 20 significant digits.
