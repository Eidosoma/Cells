# FR-43 part 2 references: notes

The inputs are the specification's folder (README.md, LAWS.md, READOUTS.md, CRITERIA.md and the eight
world files, copied verbatim to `worlds/`), as amended on 23 November 2026, and the law sections it
names. Nothing from the engine was read, run or compared.

## Sections implemented

From `docs/TEMPLATED_POLYMERISATION_LAWS.md`:
- §0, units and constants: amounts in fmol, c = n/V in mM, and c₁ = 10¹⁵/(N_A V). Free energies:
  1 fmol × 1 kJ/mol = 1 pJ.
- §1.2, §1.4 and §2: the pools, machines and complexes; the moieties with the residues in transit
  counted, used as checks; the moves.
- §3.1, the potentials: μ°_R,res = μ°_R/L_R per residue in transit, with no concentration term.
- §3.4, each move's ΔG and the heat classes H_tx, H_deg,R and H_rc. Each stage exit books
  r(−ΔG_tx), and the last also books −ΔG_rel,R = −RT ln a_R.
- §4.1, initiation, with u = 1 because no factor is declared.
- §4.2, the stages, with their per-residue factor.
- §4.3, release; §4.4, degradation; §4.5, recharging, with share 2.
- §4.7, the equations of motion.
- §4.8, the identities, used as checks.
- §3.2, the reduction, is not needed: both worlds are in the neutral form.
- §4.6, the regulator: X is not a regulator in these worlds. No factor and no turnover is declared,
  and X is written only by the network.

From the specification's LAWS.md: the driven mass-action law and its work booking; the passive
detailed-balance law and its heat booking; the water law with the held bath's work and water's heat;
U(V); the potentials and temperature, with R = N_A k_B. From READOUTS.md: every readout and its
amended definitions (the books of N, F's potentials and scope, and heat and work).

## Readings

Every reading below that the amendment of 23 November 2026 settled is marked (amended).

1. **The scheduled values** (amended): `tx` is k_I in 1/(mM s), `deg_R` is k_s in 1/s, and
   `recharge` is the capacity V_C in mM/s.
2. **N's moves** (amended): initiation moves no row. Each transcription stage exit draws r = 150 N
   and releases 2r Pi, since `draws` and `releases` are per residue. The last exit also releases one
   R and returns its machine.
3. **The gene unit's books of N** (amended):
   - gene_produced_N = ∫ max(J_C, 0);
   - gene_consumed_N = r ∫ S_tx + ∫ max(−J_C, 0), with S_tx kept signed.

   The sign split is computed exactly. A first pass locates every sign change of J_C, and a second
   pass makes those times step ends. Each increment of the smooth signed integral ∫ J_C between ends
   then belongs whole to one side. The sign changes found are listed in each file's `method`. The
   check `recharging_split_vs_signed_integral_fmol` confirms that the split adds back to ∫ J_C.
4. **The network's books of N**: the driven route is one-way. N + X → W adds ∫ J to the consumed
   side, and X → N adds it to the produced side.
5. **F's potentials** (amended). The term λ_s = μ°_s/RT − ln c0 comes from the registry where it
   declares the row, else from the network at its own c0, else it is 0. The values used:
   - C2.6: λ = 0 for Na, K, Cl, S, A and B, and λ_C = −1;
   - C2.8: λ = 0 for K, Y and X; λ = μ°/RT − ln 1000 for M, ATP, ADP, Pi, N and R; λ_W = 17.959447662019365.
6. **F's scope** (amended): the species rows only. The residues in transit (§3.4's μ°_res W) are
   left out of F, and are added back only in the energy-identity check.
7. **Osmolytes** (amended): the species rows only, traces included. The machines and complexes are
   not osmolytes.
8. **Heat and work** (amended): a driven route books work ∫ J ΔG_r and no heat; a passive route books
   heat −∫ J ΔG_r and no work. ΔG_r takes the network's potentials at its c0 of 1 mM and the
   current volume.
9. **R** (amended) is the double-precision product N_A k_B = 8.31446261815324 J/(mol K).
10. **The cited standard free energies** (amended) are not read. Every rate and heat uses the species
    potentials, and the agreement is recorded below.
11. **The volume** enters every concentration at its current value:
    - in c₁ and so in initiation's c_T;
    - in the saturations and the potentials;
    - in recharging's prefactor V V_C;
    - in the network's rate and ΔG;
    - in the osmotic pressure.

    Degradation is first order in n_R, and reads V only through ΔG_deg.
12. **`network_route_rate_fmol_per_s` in C2.6**: the passive route's net rate J. READOUTS.md's
    m k V Π c^α is the driven route's form.
13. **The volume bounds** (0.5 and 3.0 pL) are never reached. In C2.6, V stays within
    [1, 2.504] pL.
14. **Trial states.** A stiff solver's Newton iterate can try a non-positive amount. The logarithm
    then returns NaN, and the solver rejects and shortens the step. No accepted step has a
    non-positive amount.

## The gene unit's state, by name (all in fmol)

| Name | Meaning |
| --- | --- |
| `gene_state.free_machines.pol` | F_pol, the free polymerases |
| `gene_state.complexes.tx.stage_j` | C_tx,j for j = 1 to 8 |
| `gene_state.engaged.tx` | E_tx = Σ_j C_tx,j |
| `gene_state.residues_in_transit.tx` | W_tx = r Σ_j (j − 1) C_tx,j (residues) |
| `gene_state.initiations.tx` | ∫ J_I |
| `gene_state.stage_exits.tx` | ∫ S_tx (signed) |
| `gene_state.releases.tx` | ∫ Q_tx |
| `gene_state.degradations.deg_R` | ∫ D_R |
| `gene_state.turnovers.recharge` | ∫ J_C (signed, net) |

## Declared values checked for consistency

- **The gene unit's potentials** equal the registry's in every world. The network's potential for N
  is the registry's converted from 1000 mM to 1 mM, to the last digit.
- **deg_R's cited ΔG°** (−26610.24 kJ/mol, temperature-independent) over RT, with R = N_A k_B, is
  −10319.123756415123. L_R μ°_M − μ°_R is −10319.123756415122. They differ by 1.8e-12 RT.
  - With the first version's R = 8.314462618, the difference was 1.9e-7 RT.
- **Recharging's cited ΔG°/RT** (0.048790164169432) equals μ°_N + 2μ°_ADP − μ°_M − 2μ°_ATP to
  1.6e-16.
- **"The bath holds 0.4 of the cell's osmolarity"** is 0.4 of the cell's background ions:
  - C2.6: 120 mM against 300 mM of Na, K and Cl;
  - C2.8: 112 mM against 280 mM of K and Y.

  Against every osmolyte the ratios are 120/340.001 = 0.353 and 112.0/300.55 = 0.373. The
  references use the declared amounts.
- **A computed property of C2.3, not an inconsistency.** In both kinds the gene unit's elongation
  spends N within a fraction of a second.
  - n_N falls from 5 fmol to 3.968 fmol by t = 0.1 s and to about 1e-6 fmol by t = 0.3 s
    (1.0706e-6 in the sink, 1.2324e-6 in the source).
  - From then on N sits near transcription's equilibrium (x_tx → 0), at about 2e-8 fmol.
  - Recharging runs backward until t = 0.04796 s and forward after.
  - So every C2.3 quantity's largest value over the sample times is at t = 0, or is set within the
    first second. In CRITERIA.md's normalisation, the planted references (k × 1.01) differ from the
    correct ones by:

    | Quantity | Sink | Source |
    | --- | --- | --- |
    | Network books | 1.0e-2 | 9.7e-3 |
    | Route rate | 1.0e-2 | 1.0e-2 |
    | Gene unit's net books | 7.4e-7 | 5.3e-4 |
    | n_N | 3.8e-15 | 6.6e-12 |
