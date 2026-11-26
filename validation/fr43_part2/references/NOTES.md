# FR-43 part 2 references: notes

The inputs are the specification's folder (README.md, LAWS.md, READOUTS.md, CRITERIA.md and the eight
world files, copied verbatim to `worlds/`), as amended on 23 November 2026 (amendments 1 and 2), and
the law sections it names. Nothing from the engine was read, run or compared.

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

Every reading below that an amendment of 23 November 2026 settled is marked (amended) or
(amendment 2).

1. **The scheduled values** (amended): `tx` is k_I in 1/(mM s), `deg_R` is k_s in 1/s, and
   `recharge` is the capacity V_C in mM/s.
2. **The pools' machines** (amendment 2): a count of molecules in the cell, like a chain's template
   copies.
   - So M_q = machines × 10¹⁵/N_A fmol. Here 100 copies is 1.6605e-7 fmol, the free machines' initial
     amount.
   - F_q, the complexes and every flux stay in fmol.
3. **N's moves** (amended): initiation moves no row. Each transcription stage exit draws r = 150 N
   and releases 2r Pi, since `draws` and `releases` are per residue. The last exit also releases one
   R and returns its machine.
4. **The gene unit's books of N** (amended):
   - gene_produced_N = ∫ max(J_C, 0);
   - gene_consumed_N = r ∫ S_tx + ∫ max(−J_C, 0), with S_tx kept signed.

   The sign split is computed exactly. A first pass locates every sign change of J_C, and a second
   pass makes those times step ends. Each increment of the smooth signed integral ∫ J_C between ends
   then belongs whole to one side. The sign changes found are listed in each file's `method`. The
   check `recharging_split_vs_signed_integral_fmol` confirms that the split adds back to ∫ J_C.
5. **The network's books of N**: the driven route is one-way. N + X → W adds ∫ J to the consumed
   side, and X → N adds it to the produced side.
6. **F's potentials** (amended). The term λ_s = μ°_s/RT − ln c0 comes from the registry where it
   declares the row, else from the network at its own c0, else it is 0. The values used:
   - C2.6: λ = 0 for Na, K, Cl, S, A and B, and λ_C = −1;
   - C2.8: λ = 0 for K, Y and X; λ = μ°/RT − ln 1000 for M, ATP, ADP, Pi, N and R; λ_W = 17.959447662019365.
7. **F's scope** (amended): the species rows only. The residues in transit (§3.4's μ°_res W) are
   left out of F, and are added back only in the energy-identity check.
8. **Osmolytes** (amended): the species rows only, traces included. The machines and complexes are
   not osmolytes.
9. **Heat and work** (amended): a driven route books work ∫ J ΔG_r and no heat; a passive route books
   heat −∫ J ΔG_r and no work. ΔG_r takes the network's potentials at its c0 of 1 mM and the
   current volume.
   - In C2.8 N stays near 5 fmol, so spend_N's ΔG_r stays negative: about −17 RT at t = 0. The
     network's work falls monotonically, to −0.84868 pJ at 40 s.
   - `gene_heat_pJ` is H_tx + H_deg,R + H_rc. It is non-decreasing, since every move of the gene
     unit is thermodynamically consistent.
10. **R** (amended) is the double-precision product N_A k_B = 8.31446261815324 J/(mol K).
11. **The cited standard free energies** (amended) are not read. Every rate and heat uses the species
    potentials, and the agreement is recorded below.
12. **Every rate reads the current volume** (amendment 2 states this as the rule). V enters:
    - c₁ and so initiation's c_T;
    - the saturations and the potentials;
    - recharging's prefactor V V_C;
    - the network's rate and ΔG;
    - the osmotic pressure.

    Degradation is first order in n_R, and reads V only through ΔG_deg.
13. **`network_route_rate_fmol_per_s` in C2.6**: the passive route's net rate J. READOUTS.md's
    m k V Π c^α is the driven route's form. J changes sign between t = 16 and 16.5 s. The
    network's heat, −∫ J ΔG, is non-decreasing through the reversal.
14. **The volume bounds** (0.5 and 3.0 pL) are never reached. V stays within [1, 2.5039] pL in
    C2.6 and within [1, 2.4677] pL in C2.8.
15. **Trial states.** A stiff solver's Newton iterate can try a non-positive amount. The logarithm
    then returns NaN, and the solver rejects and shortens the step. No accepted step has a
    non-positive amount.

## The gene unit's state, by name (all in fmol)

| Name | Meaning |
| --- | --- |
| `gene_state.free_machines.pol` | F_pol, the free polymerases; F_pol(0) = M_q = 1.6605e-7 |
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

## Computed properties (amendment 2)

- **The network is N's main writer.**
  - The pool holds 1.6605e-7 fmol of machines. Transcription therefore draws at most about 4e-6
    fmol/s of N (r S), and initiation runs at 7e-9 fmol/s.
  - The network's route runs at 2.5e-3 fmol/s at t = 0 in the sink, and 5e-4 fmol/s in the source.
  - Recharging is in between, at |J_C| ≤ 8.1e-5 fmol/s.
- **Recharging** runs backward from t = 0, where ΔG_rc = +0.0488 RT:
  - in the sink, until t = 36.43630 s, then forward (36.26698 s in its planted twin);
  - in the source and in C2.8, throughout.
- **At 600 s:**
  - sink: n_N = 3.85094 fmol; the network has consumed 1.15424 fmol of N;
  - source: n_N = 5.28590 fmol; the network has produced 0.29118 fmol of N.
- **The planted references** (k × 1.01) differ from the correct ones, in CRITERIA.md's normalisation,
  by:

  | Quantity | Sink | Source |
  | --- | --- | --- |
  | n_N | 1.8e-3 | 5.3e-4 |
  | Gene unit's net books | 1.4e-2 | 3.6e-3 |
  | Network books | 7.7e-3 | 9.7e-3 |
  | Route rate | 1.0e-2 | 1.0e-2 |

## Superseded outputs

The tags `fr43-part2-references-c23-2026-11-23` (ae093457) and
`fr43-part2-references-c26-c27-2026-11-23` (a62d9037) are superseded. Two changes supersede them:
1. **The hash-order fix** (6d1f76f5). The network's ν had been built from a set of species names,
   whose order follows Python's per-process string hashing. That changed the last bits of every
   output, by about 1e-13.
2. **Amendment 2** (d65d7a5f). The pools' machines are now counts, not fmol.
   - C2.3, its planted twins and C2.8 change at order 1.
   - C2.6 has no pool: its arrays and checks are bitwise the same as at 6d1f76f5. Only its run
     times and provenance differ.

Every current file is generated from d65d7a5f, with no dirty code or inputs.

**The method choice under the first reading.** The first reading took the machines as fmol (100
fmol of polymerase).
- The gene unit was then stiff: it spent N within 0.3 s. So C2.3 and C2.8 were checked by BDF, a
  stiff method family.
- C2.8 needed Radau at rtol 1e-13, because recharging and the stage exits (about 3e-3 fmol/s each)
  cancelled to 1e-7 in the gene unit's net rate.

Under amendment 2 neither occurs. Every case uses one recipe: Radau at 1e-11, checked by DOP853 at
1e-13 and by Radau at 1e-12.
