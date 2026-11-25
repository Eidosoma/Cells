# Templated polymerisation: the declared equations

*Status: proposed, 20 November 2026, by the gene-regulation lane (D235), for the lead's review and
the tag `gr1-sheet-<date>`. Nothing here is registered.*

**What this sheet is.**
- **Its laws.** It states option A's laws in physical terms only. A code-blind agent can write G2's
  references from it alone, with no code and no engine output.
- **Its forms.** The built form is the neutral reduction (GENE_REGULATION_DESIGN §7.4). The charged
  form is stated once beside it, and §3.2 shows the reduction is exact while pH and free Mg²⁺ are
  held.
- **Its potentials.** It is symbolic in the potentials and names no potential-set version. Four
  symbols carry them: the fuel's ATP hydrolysis and three reaction energies of the world's own
  rows. The references are functions of the four over declared ranges, and the registration names
  each value after a direct read of its source (§3.3).
- **Its check.** `validation/gene_regulation/sheet_check.py`.

**Basis.**
- GENE_REGULATION_DESIGN §7: the arms, the non-claims and the build plan, as D235 chose.
- The kinds owner's answers on §7.5's desk question (20 November 2026), which confirm per-residue
  terms (§4.2).

**Words used.**
- **Declared:** a value or form this sheet sets. **Declared, uncited:** a declared value with no
  source; it is ours.
- **Cited:** read in a source. §8 says how each was read: the abstract, a curated record, or a
  secondary statement.
- **Derived:** computed here from declared and cited values. The check recomputes every derived
  value the sheet types.
- **Row:** an amount of the cell that other mechanisms may read. **Pool:** an amount the operator
  owns, which no other mechanism reads.
- **Move:** one unit of progress of a law. It is a residue added, a chain released, a molecule
  degraded or a recharging turnover.
- **Limit:** a closed form's value with its factors frozen at the initial state, and with machines
  abundant where §5 says so. A limit is compared within a declared bound (§5).

## 0. Conventions

**The cell.**
- One cell: a node of fixed volume V, with no growth, no division and no water flux.
- Its other rows (background ions, the cell's charge) are the world's. No law here reads or moves
  them.

**Units.**
- Amounts n are in fmol per cell. Concentrations c = n/V are in mM, since 1 fmol/pL = 1 mM.
- One molecule is 10¹⁵/N_A fmol. c₁ = 10¹⁵/(N_A V) mM is one copy's concentration (V in pL).
- Rates are in s⁻¹, fluxes J in fmol/s and time t in s, from 0.
- Free energies are in kJ/mol per unit of progress. An amount times a free energy is in pJ:
  1 fmol × 1 kJ/mol = 1 pJ.

**Constants.**
- N_A = 6.02214076 × 10²³ mol⁻¹ and k_B = 1.380649 × 10⁻²³ J/K, both exact (SI 2019); R = N_A k_B.
- T = 310.15 K (declared). So RT = 2.57873058 kJ/mol.

**Potentials and free energy.**
- The standard state is c° = 1 M for every potential and entry in this sheet. Activity a = c/c°,
  with c in M (mM/1000).
- μ_s = μ°_s + RT ln a_s per molecule of row s.
- A world at another standard concentration c₀ (mM) moves each row's μ°/RT by ln(c₀/1000 mM),
  once per molecule. It moves an entry by (Σν) ln(c₀/1000 mM).
- A move's ΔG = Σ ν_s μ_s, with ν signed and products positive. x = ΔG/RT.
- Water is at unit activity and is omitted from every stoichiometry.
- Heat is H = −ΔG per unit of progress. The second law is J·ΔG ≤ 0.

**pH and magnesium.**
- h = 10^(−pH) M is the free proton concentration; m is free Mg²⁺ in M.
- The neutral form holds both, at **pH 7.0 and m = 1.0 mM** (declared; pMg 3). These are the
  conditions of the recharging entry (§3.3).

## 1. Rows, pools and forms

### 1.1 The neutral rows (A's built form)

| Row | Stands for | Valence | Who writes and reads it |
| --- | --- | --- | --- |
| `X` | The regulator: an inducer or transcription factor, lumped | 0 | D150's turnover writes it. B1′'s factor reads it (§4.6) |
| `ATP`, `ADP`, `Pi` | The fuel, as neutral formula units: each anion with its bound counter-cations | 0 | Translation and recharging |
| `N` | The four NTPs as one lump: transcription's monomer and its own fuel | 0 | Transcription and recharging |
| `M` | The four NMPs as one lump | 0 | mRNA degradation and recharging |
| `A` | The twenty amino acids as one lump | 0 | Translation and protein degradation |
| `R` (`R_g` for gene g) | One mRNA molecule of L_R residues | 0 | Transcription releases it; translation reads it as template; degradation removes it |
| `P` (`P_g`) | One protein molecule of L_P residues | 0 | Translation releases it; degradation removes it |

Every row is strictly positive. An absent product starts at a declared trace (§5).

### 1.2 The operator's pools

- **Machines.** F_q is the free machines of pool q, in fmol: q = pol for the RNA polymerases, and
  q = rib for the ribosomes. M_q is the pool's declared total.
- **Complexes.** C_ρ,j is the complexes in stage j = 1, …, m_ρ of route ρ, in fmol.
  - Each complex holds one engaged machine and (j − 1) r_ρ residues of its growing chain.
  - The routes are tx_g (transcription of gene g) and tl_g (translation of its mRNA).
- **Residues in transit.** `R_res` and `P_res` are one residue in a growing mRNA or protein.
  W_ρ = r_ρ Σ_j (j − 1) C_ρ,j is the residues in transit on route ρ, in fmol.
- **Templates.** For transcription, the template is the gene's copies T_g: an integer, declared
  data, never a moved amount. For translation, it is the mRNA row.
- **Free energy.** Machines and templates carry none. A residue in transit carries its per-residue
  standard potential and no concentration term (§3.1).

### 1.3 The charged form, stated once

These are the same rows with their real charges.
- Each row's base form is its least-protonated, Mg-free form.
- The row holds the total over its forms, which are at equilibrium with free H⁺ and Mg²⁺ (seam C's
  convention).

| Row | Base form | z_base | Forms |
| --- | --- | --- | --- |
| `ATP` | ATP⁴⁻ | −4 | The named source's, for example Mg·ATP |
| `ADP` | ADP³⁻ | −3 | The source's |
| `Pi` | HPO₄²⁻ | −2 | The source's, for example H·Pi |
| `N` | NTP⁴⁻ | −4 | The charged arm's declaration |
| `M` | NMP²⁻ | −2 | The charged arm's declaration |
| `A` | The amino acid, as a zwitterion | 0 | None |
| `R` | The mRNA, one charge per residue | −L_R | None |
| `P` | The protein, backbone only | 0 | None |
| `R_res` | An mRNA residue in transit | −1 | None |
| `P_res` | A protein residue in transit | 0 | None |
| `H⁺` | The free proton | +1 | — |
| `Mg²⁺` | Free magnesium | +2 | — |
| `X` | The regulator | 0 | None |

**A row's forms.**
- A form f carries n_H,f protons and n_Mg,f magnesium ions on the base.
- Its dissociation constant is K_f = [base] h^(n_H,f) m^(n_Mg,f)/[f], in M^(n_H,f + n_Mg,f).
- Its standard potential is μ°_f = μ°_base + n_H,f μ°_H + n_Mg,f μ°_Mg + RT ln K_f, at 1 M.
- The binding polynomial is P(h, m) = 1 + Σ_f h^(n_H,f) m^(n_Mg,f)/K_f. The base form's
  concentration is c_tot/P.

**Declared reductions of the charged form.**
- Each RNA residue carries one phosphate and one charge. The chain's ends (the 5′ triphosphate and
  the terminal charges) are not counted.
- The amino-acid and protein lumps carry no side-chain charge.
- The polymers bind no Mg²⁺.

**The residues in transit carry their charge.** In the charged form, the node's charge must count
W_tx's −1 per residue, so the operator's pools are part of the node's charge. This is a requirement
on the charged arm, not on A.
- **For the charged arm's pricing:** it needs a field-side owner for the charge held in transit.
- The operator contract reports the compartments an operator's routes charge
  (`charged_compartments`). It has no hook for charge an operator holds in its own pools.
- That piece stands beside G5's two (GENE_REGULATION §7.10) and is not priced there.

### 1.4 Moieties

<!-- moieties -->
| Moiety | `N` | `M` | `A` | `ATP` | `ADP` | `Pi` | `R` | `P` | `R_res` | `P_res` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adenine | | | | 1 | 1 | | | | | |
| phosphorus | 3 | 1 | | 3 | 2 | 1 | L_R | | 1 | |
| nucleoside | 1 | 1 | | | | | L_R | | 1 | |
| amino acid | | | 1 | | | | | L_P | | 1 |
<!-- /moieties -->

- A weight is per molecule of the row, and per residue for `R_res` and `P_res`. Each moiety's
  total counts the residues in transit.
- Water and the proton carry no moiety here. Charge conservation covers the proton (§2).
- Magnesium is a moiety of the charged form only, and no base-form move carries Mg²⁺.
- The machines are conserved by pool: F_q + Σ over the routes on q of Σ_j C_ρ,j = M_q.

## 2. The moves

<!-- moves -->
| Species | z, charged | `tx` | `tl` | `rel_R` | `rel_P` | `deg_R` | `deg_P` | `rc` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `N` | −4 | −1 | | | | | | +1 |
| `M` | −2 | | | | | +L_R | | −1 |
| `A` | 0 | | −1 | | | | +L_P | |
| `ATP` | −4 | | −4 | | | | | −2 |
| `ADP` | −3 | | +4 | | | | | +2 |
| `Pi` | −2 | +2 | +4 | | | | | |
| `R` | −L_R | | | +1 | | −1 | | |
| `P` | 0 | | | | +1 | | −1 | |
| `R_res` | −1 | +1 | | −L_R | | | | |
| `P_res` | 0 | | +1 | | −L_P | | | |
| `H` (H⁺, the charged form only) | +1 | +1 | +4 | | | +L_R | | |
<!-- /moves -->

**Each column is one unit of progress.**
- `tx`: one residue added to a growing mRNA.
  - An NTP becomes a residue in transit.
  - Its pyrophosphate is hydrolysed at once to two phosphates.
- `tl`: one residue added to a growing protein.
  - An amino acid becomes a residue in transit, and four ATP become ADP and Pi.
  - Two of the four are aminoacylation, ATP → AMP + PPi, with adenylate kinase folded in
    (AMP + ATP → 2 ADP).
  - The other two are the elongation factors' two GTP, counted as ATP.
- `rel_R`, `rel_P`: release of one finished chain. L residues in transit become one molecule of the
  product row, and the machine returns to its pool.
- `deg_R`: one mRNA molecule hydrolysed to L_R NMPs. `deg_P`: one protein molecule hydrolysed to
  L_P amino acids.
- `rc`: one recharging turnover, NMP + 2 ATP → NTP + 2 ADP. It is two phosphoryl transfers, an NMP
  kinase and a nucleoside-diphosphate kinase, lumped.
- **Initiation moves no row.** A free machine becomes a stage-1 complex: F_q → C_ρ,1.

**A route's stages.**
- Route ρ has m_ρ stages and r_ρ = L_ρ/m_ρ residues per stage. r_ρ is an integer: m_ρ divides L_ρ.
- A complex leaving stage j < m_ρ makes r_ρ `tx` (or `tl`) moves and enters stage j + 1.
- A complex leaving stage m_ρ makes r_ρ moves and then one release.
- So one passage makes L_ρ residue moves and one release.

**Charge (the charged form).**
- Every column's Σ ν z is zero, with the residues in transit counted. So no move changes a node's
  charge, and the field sees no difference between the forms.
- The protons released are one per residue in transcription, four per residue in translation, and
  L_R per mRNA degraded.

**Declared reductions, in both forms.**
- One NTP lump, one NMP lump and one amino-acid lump.
- PPi is hydrolysed at once. GTP is counted as ATP. AMP is folded by adenylate kinase.
- Initiation's own costs (promoter opening, the initiation factors) are not drawn.
- A chain's L residue moves stand for its L − 1 bonds and its ends.

## 3. Free energies

### 3.1 The potentials, symbolic

- Each row's standard potential is a symbol: μ°_s for the charged base form, μ′°_s for the neutral
  row.
- A polymer's potential is per residue: μ°_R = L_R μ°_R,res and μ°_P = L_P μ°_P,res, at c° = 1 M.
- A residue in transit is at μ°_R,res or μ°_P,res, with no concentration term. It sits in one
  chain, not in solution.
- Only the moves' ΔG enter the laws, and every move conserves every moiety (§1.4). So each
  moiety's reference is a convention, and it cancels.

### 3.2 The reduction: neutral potentials from charged ones

At free proton h and free Mg²⁺ m, each neutral row's standard potential is its charged base
form's, transformed:

  μ′°_s(h, m) = μ°_s − RT ln P_s(h, m) − z_s μ_H(h), with μ_H(h) = μ°_H + RT ln(h/c°).

- **Its terms.** The first two are the row's free base form at equilibrium with its forms. The third
  is its proton term.
- **It is Alberty's transformed potential** (named from memory, not read):
  - the form is −RT ln Σ_f exp(−(μ°_f − N_H(f) μ_H − N_Mg(f) μ_Mg)/RT), the sum over the row's
    forms, the base included;
  - each form's proton content is counted from the base form's charge, N_H(f) = z_base + n_H,f, and
    N_Mg(f) = n_Mg,f;
  - Alberty counts every hydrogen atom instead, and the two differ by a constant per row, which
    cancels in every balanced move.
- **Why the reduction is exact.** It rests on two facts:
  - every move conserves charge, so a base-form move's protons are ν_H = −Σ ν_s z_s (§2);
  - no base-form move carries Mg²⁺.

  So, for any totals c_s and the same (h, m):

      ΔG_charged = Σ ν_s [μ°_s + RT ln(c_s/(P_s c°))] + ν_H μ_H(h)
                 = Σ ν_s [μ′°_s + RT ln(c_s/c°)] = ΔG_neutral.

- **Held.** The identity needs the neutral potentials at the state's own h and m.
  - The neutral form holds both.
  - The charged form lets them drift, and that drift is the charged arm's content (GENE_REGULATION
    §7.4).
- **Rate laws.**
  - A law written on totals sees the same totals and the same ΔG, so it gives the same flux.
  - A law written on a free form f equals one on totals with its constant K replaced by K/θ_f. Here
    θ_f = [f]/c_tot, which is fixed while h and m are held.
- **What the check shows** (sheet_check.py, part 1). Each part has a planted error that it must
  catch:
  - (a) the transform equals the pseudoisomer sum, for every row;
  - (b) every move's ΔG is equal in both forms, over random states;
  - (c) every charged move conserves charge;
  - (d) the free-form rule holds. That the laws on totals give the same flux in both forms is a
    corollary of (b), since both forms see the same totals.

### 3.3 The entries, and where each potential comes from

**From the source the registration names.**
- These are ATP, ADP and Pi with their forms, and μ°_H. The neutral form needs only their
  transformed potentials at pH 7.0 and m = 1 mM.
- Through every move they enter as one symbol, ATP hydrolysis:
  ΔG′°_ATP = μ′°_ADP + μ′°_Pi − μ′°_ATP.
- **At the sheet's own conditions.** Any fuel value named at registration is transformed at this
  sheet's T = 310.15 K, pH 7.0 and free Mg²⁺ 1 mM, by `world_potentials`.
  - It enters as the source's base potentials in RT units and its forms' constants, or as kJ/mol
    values converted at 310.15 K on the source's basis.
  - The source's own temperature, pH and Mg²⁺ are not carried.

**The world's own rows.**
- Two references: μ°_M = 0 and μ°_A = 0 (base forms, 1 M).
- Three entries, solved in order: E_rc fixes `N`, E_pd fixes the RNA residue, and E_pep fixes the
  protein residue.
- **Each is a symbol, as ΔG′°_ATP is.** The values below are the test instance's.
  - They were read second-hand: abstracts through a summariser, or a curated record.
  - E_pd was obtained in its source by subtracting a value that its abstract does not give.
  - So the references are functions of all four symbols over the ranges below. The registration
    names each value after a direct read of its source, at the sheet's T, pH and Mg²⁺ (above).

<!-- entries -->
| Entry | Reaction, on neutral rows | Test-instance value, as read | Basis | ΔG°′/RT at 310.15 K | Read in |
| --- | --- | --- | --- | --- | --- |
| `E_rc` | M + 2 ATP → N + 2 ADP | K_obs = 1.05 for 2 ADP → AMP + ATP, on totals, at pH 7.0 and 1 mM free Mg²⁺, 38 °C | ln K_obs, carried in RT units: temperature-free (dG_RT) | +0.04879016 | Lawson and Veech 1979. The NTP and NMP lumps take adenylate kinase's constant; the diphosphate kinase step is at K = 1 (declared) |
| `E_pd` | R_res → M, per residue (the chain shortened by one, an NMP released) | −5.3 kcal/mol at 25 °C and pH 7 | kJ/mol, temperature-independent | −8.59926980 | Dickson et al. 2000: a DNA phosphodiester bond's, taken for the RNA lump (declared) |
| `E_pep` | P_res → A, per residue | −3.6 kcal/mol | kJ/mol, temperature-independent | −5.84101345 | Martin 1998, glycylglycine's overall hydrolysis, read through BioNumbers. Its conditions are not stated there |
| `G_ATP` | ATP → ADP + Pi | The named source's, transformed at registration. −32 kJ/mol in the test instance only | kJ/mol | −12.40920639 | The test instance: Wiseman et al. 2023, at pH 7, pMg 3 and 37 °C |
<!-- /entries -->

**The test values' conditions.**
- Each is taken at the world's pH 7.0 and m = 1 mM. Where a source's conditions differ or are not
  stated, that is a declared approximation of the test instance.
- The engine's solutions are ideal: an ionic strength in a source is not carried.
- kcal is the thermochemical one, 4.184 kJ.

**The neutral form's entries, as FreeEnergyEntry.** Each is on neutral rows, at integer
stoichiometry per molecule, with c₀ = 1000 mM:
- (M −1, ATP −2, N +1, ADP +2), with dG_RT = E_rc/RT (ln 1.05 in the test instance);
- (R −1, M +L_R), with dG_kJ_mol = L_R E_pd, the temperature-independent basis and offset 0;
- (P −1, A +L_P), with dG_kJ_mol = L_P E_pep.

At another c₀, an entry moves by (Σν) ln(c₀/1000 mM): L_R − 1 and L_P − 1 for the hydrolyses.

**The charged form's entries.**
- They have the same values, over base forms with their protons (`deg_R` has ν_H = L_R per
  molecule).
- Each carries dG_RT_offset = −ν_H ln(h/c°) + Σ_s ν_s ln P_s(h, m), at pH 7 and m = 1 mM. μ°_H
  cancels.
- E_rc is in RT units, and an entry in RT units takes no separate offset. So its offset, here only
  the binding polynomials' terms (ν_H = 0), is added to its dG_RT.
- The check's `entry_offset` computes the offset.

**Transcription and translation follow** (ΔG°′ of each move):
- ΔG°′_tx = 2 ΔG′°_ATP − E_pd − E_rc per residue;
- ΔG°′_tl = 4 ΔG′°_ATP − E_pep per residue;
- ΔG°′_deg,R = L_R E_pd and ΔG°′_deg,P = L_P E_pep per molecule;
- ΔG°′_rc = E_rc.

**The registration's tool.** `world_potentials` in the check takes a named source's base
potentials and forms. It returns the neutral world's potentials at the world's c₀ for ATP, ADP, Pi,
N, M, A, R and P. The world's own forms for N and M do not change the neutral result; the check's
part 3 shows it.

**The numeric test instance** (for the references, §6).
- It sets ΔG′°_ATP = −32 kJ/mol, and μ′°/RT = 0 at 1 M for ADP, Pi, M and A.
- The other potentials follow; §5.3 types them (`mu_ATP`, `mu_N`, `mu_R_res`, `mu_P_res`).

**Ranges.** Every reference is a function of the four symbols and holds for every value in these
ranges:
- ΔG′°_ATP in [−40, −25] kJ/mol;
- E_pd in [−30, −15] kJ/mol;
- E_pep in [−25, 0] kJ/mol;
- E_rc/RT in [−1, 1].

The registration may name any value within them. §5.6's bounds and domain are measured over their
corners.

**For the registration's choice of E_pep.**
- Martin's value is glycylglycine's overall hydrolysis, Gly-Gly → 2 Gly.
  - It includes the ionisation of the new termini.
  - It should also include the dipeptide's own end charges, which sit beside the bond and shift
    its ionisation. That is this sheet's reading of an unread source (S). §1.3 leaves a chain's
    ends uncounted.
- A long chain's internal bond has no such neighbouring ends. Spirin's value is one stated for a
  long chain.
- The direct read says which kind a value is, and the registration says which kind the lump takes.
  The lump's residue sits inside a chain whose ends are uncounted, and its product is a free
  zwitterion.

### 3.4 Each move's ΔG, and the account as a state function

G(state) = Σ_rows n_s [μ°_s + RT (ln a_s − 1)] + Σ_ρ μ°_ρ,res W_ρ   (pJ: n in fmol, μ in kJ/mol)

**Its scope.**
- G sums over the operator's rows (N, M, A, ATP, ADP, Pi, each R_g and each P_g) and the residues in
  transit.
- X and the cell's background are not in it.
- ∂G/∂n_s = μ_s. So each move's ΔG is G's change per unit of progress.

**Each move's ΔG:**
- per `tx` residue: ΔG_tx = μ°_R,res + 2 μ_Pi − μ_N;
- per `tl` residue: ΔG_tl = μ°_P,res + 4 μ_ADP + 4 μ_Pi − μ_A − 4 μ_ATP;
- per release: ΔG_rel,R = μ_R − L_R μ°_R,res = RT ln a_R, and likewise for P;
- per degradation: ΔG_deg,R = L_R μ_M − μ_R and ΔG_deg,P = L_P μ_A − μ_P;
- per recharging turnover: ΔG_rc = μ_N + 2 μ_ADP − μ_M − 2 μ_ATP.

**The stages.**
- A stage exit j < m books r ΔG_tx. The last books r ΔG_tx + ΔG_rel.
- One passage telescopes: L_R ΔG_tx + ΔG_rel,R = μ_R + 2 L_R μ_Pi − L_R μ_N, the net move's ΔG.
  The same holds for translation.

**The heat classes.** Each is in pJ, from t = 0:
- **H_tx:** every transcription stage exit books r_tx (−ΔG_tx), and an exit from the last stage also
  books −ΔG_rel,R. So H_tx's rate is r_tx S_tx (−ΔG_tx) + Q_tx (−ΔG_rel,R), with S and Q from §4.7.
- **H_tl:** the same for translation, with ΔG_tl and ΔG_rel,P.
- **H_deg,R, H_deg,P and H_rc:** each flux times its −ΔG.
- Initiation books none. So a release's heat is in its route's class.
- In the two-gene world each class sums over the genes.

**The identity.** No work is done on these rows: there is no regenerator and no driven route. So
G(t) − G(0) + H_tx + H_tl + H_deg,R + H_deg,P + H_rc = 0, and each class is non-negative and
non-decreasing inside the domain.

### 3.5 The domain

- **One-sided.** Each residue move and each degradation runs forward only:
  - x_tx ≤ x_dom and x_tl ≤ x_dom per residue;
  - ΔG_deg/(L RT) ≤ x_dom;
  - with x_dom = −1 (declared, uncited).

  A state outside the domain is refused, never repaired (GENE_REGULATION §7.5).
- **The release.** ΔG_rel ≤ 0, so c_R and c_P stay at or below c° = 1 M.
- **Recharging is two-sided.** It reverses where ΔG_rc > 0.
- **A's arms sit far inside the domain.** At A1's start, x_tx ≈ −20.6 and x_tl ≈ −68.0 per residue;
  the degradations are at −18.5 and −12.0 per residue (§5.3).

## 4. Rate laws

### 4.1 Initiation

  J^I_ρ = u_ρ(t) k_I,ρ c_T,ρ F_q   (fmol/s)

It is mass action in free machines and template.
- **The template's concentration.** For transcription it is c_T = T_g c₁, from the gene's copies.
  For translation it is c_T = c_R,g, the mRNA's concentration.
- **k_I,ρ** (mM⁻¹ s⁻¹) is the scheduled maximum, piecewise constant. It is the routable control
  `initiation_rate` (B1′).
- **u_ρ in [b, 1]** is the coupling's factor (§4.6). It is 1 where no coupling is declared.
  - In A1 only transcription's initiation carries u. Translation's carries none: §5.3's λ_tx
    includes u₁, and β_tl does not.
- **λ_ρ = u_ρ k_I,ρ c_T,ρ** (s⁻¹) is one free machine's initiation rate on the route.
- **Initiation moves no row and books nothing** (declared). The free energy of promoter binding and
  of the initiation factors is outside the model, as is the machinery's other cost (seam E's fuel
  block).

### 4.2 Elongation: the stages, with per-residue terms

  J_ρ,j = κ_ρ C_ρ,j φ_ρ,  κ_ρ = v_ρ/r_ρ,  φ_ρ = Π_{d in D_ρ} [c_d/(K_ρ,d + c_d)] × (1 − e^(x_ρ))

**Its terms.**
- **The draws.** D_tx = {N}, and D_tl = {A, ATP}. Each draw saturates in its row, so a draw slows as
  the row runs short.
- **x_ρ** is the per-residue affinity: ΔG_tx/RT or ΔG_tl/RT (§3.4).
  - The release's term is not in the factor. It is booked with the last stage.
- **v_ρ** is the speed in residues per second, at saturating draws and far from equilibrium.

**Why a per-residue factor.**
- One residue added is the elementary step, with forward rate w⁺ and backward rate w⁻ = w⁺ e^(x).
  A walk of such steps has mean velocity w⁺ (1 − e^(x)) (S).
- So a stage of r residues runs at κ φ. It carries the factor (1 − e^(x)), not (1 − e^(r x)).
- This equals the monomial form's affinity share at n = r.
- The kinds owner confirmed on 20 November that per-residue terms are the form for expression, at
  shares of 10²–10³. The share cap of 8 stays, and no closed geometric form is wanted.

**The chain's timing.**
- All stages read the same rows, so they share one rate.
- So the dwell in the chain is Erlang(m, κφ), with mean τ = L/(v φ) and variance τ²/m.

### 4.3 Release

At J_ρ,m:
- one product molecule enters its row (+J_ρ,m);
- one machine returns to F_q.

A machine is returned at every release. A chain that declares §9's release step instead puts its
completed molecule in a hold, and releases it from there into one of two fate rows.

### 4.4 Degradation

  J^D_s = k_s n_s (1 − e^(ΔG_deg,s/(L_s RT)))   (fmol/s), for s = R_g and P_g

- It is first order, with the per-residue factor, and returns L_s monomers.
- It draws no fuel (declared). The proteasome's ATP is a cost of the machinery, for seam E's fuel
  block.
- It does not depend on ribosome load. A complex on a degraded mRNA still finishes its chain
  (declared: no premature termination).
- k_s is scheduled and piecewise constant.

### 4.5 Recharging

  J^C = V V_C [c_M/(K_C,M + c_M)] [c_ATP/(K_C,ATP + c_ATP)] (1 − e^(ΔG_rc/(2 RT)))   (fmol/s)

- **It is the operator's own route** (GENE_REGULATION §7.5), so the operator is the one writer of N
  and M.
- **Its share is 2:** the elementary step is one of the two phosphoryl transfers.
- **It is two-sided.**
- **There is no ADP-to-ATP regeneration.** It is not the operator's, and A's worlds declare none.
  So ATP, ADP and Pi are finite pools, written only by translation and recharging.

### 4.6 The regulator and its factor

- **X follows D150's law,** `scheduled_species_turnover@1`:
  - dn_X/dt = P_X(t) − k_X(t) n_X;
  - production P_X is in fmol/s and clearance k_X in s⁻¹, both piecewise constant.
- **The factor is B1′'s** `hill_activation`, through a rate route on `initiation_rate`:
  - u(t) = b + (1 − b) c_X^n/(K_X^n + c_X^n);
  - b is the basal level, K_X the half-saturation in mM, and n the Hill coefficient;
  - the scheduled k_I is the maximum.
- **The loop is open.** No product enters any factor.

### 4.7 The equations of motion

**The chain, per route ρ:**
- dC_ρ,1/dt = J^I_ρ − J_ρ,1, and dC_ρ,j/dt = J_ρ,j−1 − J_ρ,j for j = 2, …, m_ρ;
- E_ρ = Σ_j C_ρ,j, the engaged machines;
- S_ρ = Σ_j J_ρ,j, every stage exit;
- Q_ρ = J_ρ,m, the releases.

**The regulator:** dn_X/dt = P_X − k_X n_X.

**Everything else, for one gene.** Read each row as d(amount)/dt = Σ over the columns of
coefficient × flux, with every flux in fmol/s:
- J_I_tx = J^I_tx and J_I_tl = J^I_tl, the initiations;
- S_tx, S_tl, the stage exits, and Q_tx, Q_tl, the releases;
- D_R = J^D_R and D_P = J^D_P, the degradations;
- J_C = J^C, recharging.

<!-- motion -->
| Amount | `J_I_tx` | `S_tx` | `Q_tx` | `D_R` | `J_I_tl` | `S_tl` | `Q_tl` | `D_P` | `J_C` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `F_pol` | −1 | | +1 | | | | | | |
| `E_tx` | +1 | | −1 | | | | | | |
| `W_tx` | | +r_tx | −L_R | | | | | | |
| `R` | | | +1 | −1 | | | | | |
| `N` | | −r_tx | | | | | | | +1 |
| `M` | | | | +L_R | | | | | −1 |
| `Pi` | | +2r_tx | | | | +4r_tl | | | |
| `F_rib` | | | | | −1 | | +1 | | |
| `E_tl` | | | | | +1 | | −1 | | |
| `W_tl` | | | | | | +r_tl | −L_P | | |
| `P` | | | | | | | +1 | −1 | |
| `A` | | | | | | −r_tl | | +L_P | |
| `ATP` | | | | | | −4r_tl | | | −2 |
| `ADP` | | | | | | +4r_tl | | | +2 |
<!-- /motion -->

- **What the check verifies of this table.**
  - Each column is the move matrix's composition: S as r residue moves; Q as a release plus a
    machine's return; D and J_C as their moves; J_I as a machine engaged.
  - So every column conserves the moieties and the machines.
  - Each column's free energy is its move's: r ΔG_tx for S_tx, ΔG_rel,R for Q_tx, and so on, so
    dG/dt = Σ J ΔG.
- **Several genes.** Each gene g has its own columns, with its own r and L, and its own R_g, P_g,
  E_ρ,g and W_ρ,g. The machines, N, M, A, ATP, ADP and Pi are shared, so their rates sum over the
  genes.

### 4.8 The identities

- **Machines:** F_q + Σ over the routes on q of Σ_j C_ρ,j = M_q.
- **Residues, per route:** r_ρ ∫S_ρ(t) = W_ρ(t) + L_ρ ∫Q_ρ(t).
  - S_ρ and Q_ρ are §4.7's fluxes.
  - ∫S_ρ(t) = ∫₀ᵗ S_ρ dt and ∫Q_ρ(t) are their cumulative extents: every stage exit and every
    release since t = 0.
- **Products:** n_prod(t) = n_prod(0) + ∫Q(t) − ∫D(t), with D the degradation flux.
- **Moieties:** each total over the rows and the residues in transit is constant.
- **Energy:** §3.4's identity.

## 5. The arms

### 5.1 A1, the expression unit

One gene, open loop, in a cell with no channels. The regulator comes from D150's turnover, through
B1′. A1's rows are X, N, M, A, ATP, ADP, Pi, R and P.

<!-- a1 -->
| Symbol | Value | Unit | What | Basis |
| --- | --- | --- | --- | --- |
| `V` | 1.0 | pL | The cell's volume | Declared, uncited |
| `T_copies` | 1 | copies | Gene copies, T | Declared |
| `L_R` | 1200 | nt | The mRNA's length | Declared, uncited |
| `m_tx` | 8 | 1 | Transcription's stages (r_tx = 150) | Declared, uncited |
| `v_tx` | 50 | nt/s | The polymerase's speed | Declared, within GENE_REGULATION §1.1's 40–55 nt/s |
| `L_P` | 400 | aa | The protein's length | Declared, uncited |
| `m_tl` | 8 | 1 | Translation's stages (r_tl = 50) | Declared, uncited |
| `v_tl` | 16 | aa/s | The ribosome's speed | Declared, within §1.1's 12–21 aa/s |
| `M_pol` | 1e4 | copies | RNA polymerases | Declared, uncited |
| `M_rib` | 1e6 | copies | Ribosomes | Declared, uncited |
| `k_I_tx` | 1.2e4 | mM⁻¹ s⁻¹ | Transcription's initiation, the scheduled maximum | Declared, uncited |
| `k_I_tl` | 120 | mM⁻¹ s⁻¹ | Translation's initiation | Declared, uncited |
| `K_N_tx` | 0.02 | mM | Transcription's NTP saturation | Declared, uncited |
| `K_A_tl` | 0.02 | mM | Translation's amino-acid saturation | Declared, uncited |
| `K_ATP_tl` | 0.02 | mM | Translation's ATP saturation | Declared, uncited |
| `V_C` | 0.01 | mM/s | Recharging's capacity | Declared, uncited |
| `K_M_rc` | 0.1 | mM | Recharging's NMP saturation | Declared, uncited |
| `K_ATP_rc` | 0.1 | mM | Recharging's ATP saturation | Declared, uncited |
| `k_R` | 3.0e-3 | s⁻¹ | mRNA degradation (lifetime 333 s) | Declared, uncited |
| `k_P` | 5.0e-4 | s⁻¹ | Protein degradation (lifetime 2000 s) | Declared, uncited |
| `K_X` | 1.0e-3 | mM | The factor's half-saturation | Declared, uncited |
| `n_X` | 2 | 1 | The factor's Hill coefficient | Declared, uncited |
| `b_X` | 0.02 | 1 | The factor's basal level | Declared, uncited |
| `P_on` | 2.0e-6 | fmol/s | X's production in phase 1 | Declared, uncited |
| `k_X` | 2.0e-3 | s⁻¹ | X's clearance, both phases | Declared, uncited |
| `t_off` | 10800 | s | Phase 2 starts: P_X = 0 from here | Declared |
| `t_end` | 21600 | s | The horizon | Declared |
| `c_N` | 2.0 | mM | Initial NTP | Declared, uncited |
| `c_M` | 0.05 | mM | Initial NMP | Declared, uncited |
| `c_A` | 2.0 | mM | Initial amino acid | Declared, uncited |
| `c_ATP` | 5.0 | mM | Initial ATP | Declared, uncited |
| `c_ADP` | 0.5 | mM | Initial ADP | Declared, uncited |
| `c_Pi` | 5.0 | mM | Initial Pi | Declared, uncited |
| `c_X` | 1.0e-3 | mM | Initial X: P_on/(k_X V), its phase-1 steady state | Declared |
| `c_R` | 1.0e-12 | mM | Initial mRNA, a trace | Declared |
| `c_P` | 1.0e-12 | mM | Initial protein, a trace | Declared |
<!-- /a1 -->

**The initial state.**
- Every machine is free: F_pol = M_pol and F_rib = M_rib, as amounts (copies × 10¹⁵/N_A fmol).
- There are no complexes and no residues in transit.
- The rows start at the table's concentrations, as amounts c V.

**The schedule.**
- k_I_tx, k_I_tl, k_R and k_P are constant over the run.
- Phase 1, 0 ≤ t < t_off:
  - P_X = P_on, so X holds at K_X and u = u₁ = 0.51;
  - c_X = K_X makes the Hill term exactly ½ for any n_X;
  - u₁ is far from 1, so a factor applied twice is visible (§5.4).
- Phase 2, t_off ≤ t ≤ t_end:
  - P_X = 0, so c_X = K_X e^(−k_X (t − t_off));
  - u(t) = b + (1 − b)/(1 + e^(2 k_X (t − t_off))) exactly, since n_X = 2.

**The horizon.** 21,600 s. The outputs are every 60 s, at 0, 60, …, 21,600 s.

**R-chain's closed forms: phase 1, the frozen and abundant limit.**
- **The limit's assumptions.**
  - Each factor is frozen at its initial value: φ_tx, φ_tl, and the degradations' per-residue
    factors, so k₀_R and k₀_P (§5.3).
  - The machines are abundant: F_q ≈ M_q.
  - So κ₀ = κ φ and τ₀ = L/(v φ).
- **Under it, phase 1 is linear with constant coefficients:**
  - transcription initiates at J^I_tx = λ_tx M_pol (fmol/s), with M_pol as an amount;
  - translation initiates at J^I_tl = β n_R, with β = k_I_tl M_rib c₁ (s⁻¹; `beta_tl` in §5.3).
- **The mRNA** (κ₀ > k₀_R), with P(j, y) = 1 − e^(−y) Σ_{i<j} y^i/i!, the regularized lower
  incomplete gamma function at integer j:

      n_R(t) = n_R(0) e^(−k₀_R t)
               + (J^I_tx/k₀_R) [P(m, κ₀ t) − e^(−k₀_R t) (κ₀/(κ₀ − k₀_R))^m P(m, (κ₀ − k₀_R) t)]

- **The engaged polymerases:** E_tx(t) = (J^I_tx/κ₀) Σ_{j=1}^{m} P(j, κ₀ t).
- **The whole state.** y = (C_tx,1, …, C_tx,m, n_R, C_tl,1, …, C_tl,m, n_P), all in fmol, obeys
  - C_tx,1′ = J^I_tx − κ₀_tx C_tx,1, and C_tx,j′ = κ₀_tx (C_tx,j−1 − C_tx,j);
  - n_R′ = κ₀_tx C_tx,m − k₀_R n_R;
  - C_tl,1′ = β n_R − κ₀_tl C_tl,1, and C_tl,j′ = κ₀_tl (C_tl,j−1 − C_tl,j);
  - n_P′ = κ₀_tl C_tl,m − k₀_P n_P.

  So ẏ = A y + b, with b's first entry J^I_tx, its other entries 0, and A the rest. The exact
  solution is y(t) = e^(At)(y(0) + A⁻¹b) − A⁻¹b, from y(0) = 0 except the products' traces.
- **The steady state:**
  - n_R* = J^I_tx/k₀_R;
  - n_P* = β n_R*/k₀_P;
  - E_tx* = J^I_tx τ₀_tx and E_tl* = β n_R* τ₀_tl.
- **The bound, measured (§5.6).**
  - Each closed form (n_R, n_P, E_tx and E_tl) is compared with A1's full ODE at the outputs on
    [0, t_off).
  - The tolerance is ε_A1 = 2 × 10⁻³ times the readout's steady state in the limit (n_R*, n_P*,
    E_tx* and E_tl*).
  - The largest gap measured over §3.3's ranges is 5.1 × 10⁻⁴, in n_P. It comes from the machines
    engaged, the pools' drift and the factors' change from their frozen values.
  - The references report the actual gap at the registered values. A gap above ε_A1 would resize
    the world, which would change this sheet and its tag.
- **What judges the dynamics.** A1's full ODE, with both phases, finite pools and every factor live.

### 5.2 A1-M, the machine-limited arm

Machines are scarce against templates. Monomers and fuel are in excess, so the chain's time stays at
its initial value. There is no regulator (u = 1). Every value not in this table is A1's.

<!-- a1m -->
| Symbol | Value | Unit | What | Basis |
| --- | --- | --- | --- | --- |
| `M_pol` | 100 | copies | RNA polymerases, in the polymerase-limited worlds | Declared, uncited |
| `k_I_tx` | 2.5e6 | mM⁻¹ s⁻¹ | Transcription's initiation | Declared, uncited |
| `L_2` | 2400 | nt | Gene 2's length in the two-gene world (m = 8, so r = 300) | Declared, uncited |
| `T_1` | 10 | copies | Gene 1's copies in the two-gene world | Declared |
| `T_2` | 5 | copies | Gene 2's copies in the two-gene world | Declared |
| `c_N` | 5.0 | mM | Initial NTP, in the polymerase-limited worlds | Declared, uncited |
| `M_rib` | 1000 | copies | Ribosomes, in the ribosome-limited worlds | Declared, uncited |
| `k_I_tl` | 2.4e6 | mM⁻¹ s⁻¹ | Translation's initiation | Declared, uncited |
| `c_A` | 5.0 | mM | Initial amino acid, in the ribosome-limited worlds | Declared, uncited |
| `t_end_pol` | 3600 | s | The polymerase-limited horizon, the two-gene world's included | Declared |
| `t_end_rib` | 600 | s | The ribosome-limited horizon | Declared |
| `window_pol` | 600 | s | The final window for the release rate, polymerase-limited | Declared |
| `window_rib` | 120 | s | The final window, ribosome-limited | Declared |
<!-- /a1m -->

**Polymerase-limited first: one world per copy number.**
- The copy numbers are T = <!-- sweep -->1, 2, 5, 10, 20, 50, 100<!-- /sweep -->.
- **Rows:** R, N, M, ATP, ADP and Pi. The routes are transcription, mRNA degradation and recharging;
  there is no translation.
- **Initial state:** N 5.0 mM. M, ATP, ADP and Pi are as A1's, R at A1's trace, and every
  polymerase is free.
- **Outputs:** every 30 s, from 0 to 3,600 s.
- **The sweep's span.** λ₁τ₀ = 0.1000 per copy (`M_lambda_tau_1`), so the sweep runs from 0.1 to 10
  and reaches the saturated end.

**The two-gene world.**
- Gene 1 has T_1 = 10 copies of L_R = 1200 nt. Gene 2 has T_2 = 5 copies of L_2 = 2400 nt.
- Both have m = 8, v = 50 nt/s, k_I_tx and k_R, and they share the 100 polymerases.
- Its rows are R_1, R_2, N, M, ATP, ADP and Pi.
- **Initial state:** as the polymerase-limited worlds', with R_1 and R_2 both at A1's trace.
- **Horizon and outputs:** as the polymerase-limited worlds': t_end_pol, every 30 s, with the
  window window_pol.

**Ribosome-limited second: one world per mRNA amount.**
- The mRNA is held at n_R = 1, 2, 5, 10, 20, 50 or 100 copies. Nothing writes it: there is no
  transcription and no mRNA degradation.
- The held mRNA has A1's L_R = 1200. Only its constant contribution to the phosphorus and
  nucleoside totals depends on that.
- **Rows:** R, P, A, ATP, ADP and Pi. The routes are translation and protein degradation (k_P).
- **Initial state:** A 5.0 mM, ATP, ADP and Pi as A1's, P at A1's trace, and every ribosome free.
- **Outputs:** every 10 s, from 0 to 600 s.

**R-machine's closed forms: the steady state, a limit with τ₀ frozen at the start.** Every closed
form is in fmol: M is the pool as an amount (copies × 10¹⁵/N_A), and J* is in fmol/s. Dividing by
10¹⁵/N_A gives copies.
- **One gene:** J* = λ M/(1 + λ τ₀).
  - λ = k_I c₁ T for transcription, and k_I c₁ n_R for translation.
  - It follows from three facts: Little's law, E = J τ₀; the free machines, F = M − E; and
    initiation, J = λ F.
  - J* rises linearly at small T and saturates at M/τ₀.
- **Two genes:** J*_g = λ_g M/(1 + Σ_h λ_h τ₀,h). Each gene takes its share of one budget.
- **The engaged and free machines:** E*_g = J*_g τ₀,g, and F* = M/(1 + Σ_h λ_h τ₀,h).
- **The readout.** J̄ is the release rate over the final window, in fmol/s:
  J̄ = (∫Q(t_end) − ∫Q(t_end − window))/window, with ∫Q the cumulative releases (§4.8). In the
  two-gene world it is per gene.
- **The bound, measured (§5.6).**
  - J̄, E and F at t_end are compared with the closed forms within ε_M = 2 × 10⁻⁴, relative.
  - The largest gap measured over §3.3's ranges is 5.1 × 10⁻⁵, in F. It comes from the draws'
    drift.
  - A gap above ε_M at G2 would change this sheet and its tag.
- **The transient** comes from R-share's ODE.

**Its two plants.** Each is an exact edit, and each must fail one of the arm's judged items.
1. **Initiation reads the total machines, not the free ones.**
   - The edit: J^I = λ M_q in place of λ F_q (§4.1).
   - **Registered at T = 5** (λ₁τ₀ ≈ 0.50), where the plant's free pool stays positive:
     F = M (1 − λ₁ T τ₀) ≈ M/2 at its steady state, and above it on the way.
   - There it gives J = λ M ≈ 1.5 J*, so it fails J̄ in that world by about 50 %, far beyond ε_M.
   - At T ≥ 10 the same edit drives F below zero, and the engine would refuse the step rather
     than yield a wrong J. So it is not registered there.
2. **A machine is not returned at release.**
   - The edit, in every world:
     - the `Q_tx` column's `F_pol` entry is 0 (§4.7) in the polymerase-limited and two-gene worlds;
     - the `Q_tl` column's `F_rib` entry is 0 in the ribosome-limited worlds.
   - The free pool drains as F = M e^(−λt), since no machine returns, and J̄ falls far below J*.
     It is about 14 % of J* in the ribosome-limited world at n_R = 1, where λ t_end ≈ 2.4, and
     near zero where λ t_end is large.
   - It fails F + E = M in every world, and J̄ by wide margins.

### 5.3 Derived values

They are at the numeric test instance (§3.3) and the arms' initial states. The check recomputes
each one, and each is typed to its last digit.

<!-- derived -->
| Symbol | Value | Definition |
| --- | --- | --- |
| `RT_kJ_mol` | 2.578730581 | RT at 310.15 K, kJ/mol |
| `c_1` | 1.660539067e-9 | One copy's concentration in 1 pL, mM |
| `mu_ATP` | 12.40920639 | μ′°_ATP/RT at 1 M, the test instance |
| `mu_N` | 24.86720294 | μ′°_N/RT at 1 M, the test instance |
| `mu_R_res` | 8.599269797 | μ′°_R,res/RT at 1 M, the test instance |
| `mu_P_res` | 5.841013447 | μ′°_P,res/RT at 1 M, the test instance |
| `r_tx` | 150 | L_R/m_tx |
| `r_tl` | 50 | L_P/m_tl |
| `kappa_tx` | 0.3333333333 | v_tx/r_tx, s⁻¹ |
| `kappa_tl` | 0.32 | v_tl/r_tl, s⁻¹ |
| `x_tx` | −20.64995978 | ΔG_tx/RT per residue, at A1's start |
| `x_tl` | −67.98481385 | ΔG_tl/RT per residue, at A1's start |
| `y_R` | −18.473975036 | ΔG_deg,R/(L_R RT), at A1's start |
| `y_P` | −11.969274604 | ΔG_deg,P/(L_P RT), at A1's start |
| `x_rc` | −0.8675005677 | ΔG_rc/RT, at A1's start: recharging runs forward |
| `phi_tx` | 0.9900990088 | φ_tx at A1's start |
| `phi_tl` | 0.9861543923 | φ_tl at A1's start |
| `tau_tx` | 24.240000026 | τ₀_tx = L_R/(v_tx φ_tx), s |
| `tau_tl` | 25.35100000 | τ₀_tl, s |
| `k0_R` | 0.0029999999716 | k_R (1 − e^(y_R)), s⁻¹ |
| `k0_P` | 0.0004999968320 | k_P (1 − e^(y_P)), s⁻¹ |
| `u_1` | 0.51 | u in phase 1 |
| `lambda_tx` | 1.016249909e-5 | u₁ k_I_tx c₁ T, s⁻¹ |
| `beta_tl` | 0.1992646881 | k_I_tl M_rib c₁, s⁻¹ |
| `M_phi_tx` | 0.9960159358 | φ_tx at A1-M's polymerase-limited start (N 5 mM) |
| `M_tau_1` | 24.09600001 | τ₀ of a 1200-nt gene there, s |
| `M_tau_2` | 48.19200002 | τ₀ of the 2400-nt gene, s |
| `M_lambda_1` | 0.004151347668 | k_I_tx c₁, per copy, s⁻¹ |
| `M_lambda_tau_1` | 0.10003087345 | λ₁ τ₀ per copy, the 1200-nt gene |
| `M_phi_tl` | 0.9920477453 | φ_tl at A1-M's ribosome-limited start |
| `M_tau_rib` | 25.20040000 | τ₀_tl there, s |
| `M_lambda_rib` | 0.003985293761 | k_I_tl c₁, per mRNA copy, s⁻¹ |
| `M_lambda_tau_rib` | 0.1004309969 | λ τ₀ per mRNA copy |
<!-- /derived -->

### 5.4 A1's plants

These are the plants of GENE_REGULATION §4.1. Each is an exact edit of A1, and each must fail a
judged item. The references run each plant and report the largest change in each readout, so that
the protocol can register which item each one fails.
1. **A wrong stage count.**
   - The edit: m_tx = 6, so r_tx = 200 and κ_tx = v_tx/200; everything else is unchanged.
   - It fails the stage occupancies C_tx,j: six stages, each holding a third more complexes at
     steady state. They are its detector, judged against A1's ODE.
   - E_tx and n_R move only about 10⁻³ and 10⁻⁴ of their scales, since the mean dwell L/v is
     unchanged and only its variance τ²/m differs.
   - So E_tx and n_R fail only where G6's judged tolerance against the ODE is tighter than those
     sizes, and never against ε_A1.
2. **A wrong speed.**
   - The edit: v_tx = 40.
   - τ₀ is 25 % longer, so it fails E_tx's plateau and n_R's delay.
3. **A dropped fuel term.**
   - The edit: the `S_tl` column's `ATP`, `ADP` and `Pi` entries are 0 (§4.7); the laws, φ_tl and
     ΔG_tl, are unchanged.
   - It fails ATP, ADP and Pi, and G's identity.
4. **A machine not returned.**
   - The edit: the `Q_tx` column's `F_pol` entry is 0.
   - It fails F_pol + E_tx = M_pol.
5. **A factor applied twice.**
   - The edit: u² in place of u in J^I_tx, which is 0.26 against 0.51 in phase 1.
   - It halves n_R and n_P.
6. **A wrong residue count.**
   - The edit: the `S_tl` column's `A` entry is −49, while `W_tl` gains 50 per exit and each
     release delivers L_P = 400.
   - It fails the amino-acid moiety, A's trajectory and G's identity: the column's free energy is
     no longer 50 ΔG_tl, and differs by μ_A per exit.
   - The residue identity r ∫S = W + L ∫Q still holds, since the edit leaves W's coefficients as
     they are.

The check confirms that edits 3, 4 and 6 break the identity each names (part 6). The other three
need the dynamics, so the references show them.

### 5.5 A2, the coupling to Vm (development, not judged)

- **What it is.** The protein becomes FR-7's precursor, at 1 ms with synthetic lifetimes.
- **What it waits on.**
  - the producer admitting a precursor that the operator writes;
  - FR-7's own protocol.
- **What this sheet gives it.** No references and no judged item. A2 is development.

### 5.6 The measured bounds, and the domain

**What was measured** (`sheet_check.py --bounds`, the lane's own tool; the references do not read
it):
- **The system:** §4.7's full system, by RK4 at a 0.5 s step.
  - The tool's check pass at 1 s, over the 18 edge sets below, changed no gap by more than
    2.2 × 10⁻¹⁰ of itself.
  - An earlier pass at 0.25 s agreed with 0.5 s to 6 × 10⁻¹⁰.
- **The worlds:** every world of §5.1 and §5.2. That is A1, the seven polymerase-limited worlds,
  the two-gene world and the seven ribosome-limited worlds.
- **The potential sets,** 50 of them. Eighteen are edge sets:
  - the test instance;
  - the test instance with Spirin's E_pep, −0.5 kcal/mol;
  - the 16 corners of §3.3's ranges, ΔG′°_ATP ∈ {−40, −25} kJ/mol, E_pd ∈ {−30, −15} kJ/mol,
    E_pep ∈ {−25, 0} kJ/mol and E_rc/RT ∈ {−1, 1}.
- **The interior sample:** 32 points inside the ranges, a Latin hypercube. Its points are the table
  below, so it depends on no library's shuffle.
  - They were drawn with `rng = random.Random(20261120)` (Python 3.13.5).
  - For each symbol in the order ΔG′°_ATP, E_pd, E_pep, E_rc/RT: `strata = list(range(32))`, then
    `rng.shuffle(strata)`, then, for k = 1, …, 32, value_k = low + (high − low)(strata[k − 1] +
    `rng.random()`)/32.
  - Each symbol's shuffle is followed by its 32 draws before the next symbol's shuffle. So each
    symbol has exactly one point per stratum.

<!-- interior -->
| k | ΔG′°_ATP (kJ/mol) | E_pd (kJ/mol) | E_pep (kJ/mol) | E_rc/RT |
| --- | --- | --- | --- | --- |
| 1 | -35.13975773013145 | -21.721949644970767 | -6.154455150921102 | -0.29785693923454026 |
| 2 | -36.54127768116361 | -26.752050614913355 | -15.197128815613524 | 0.5456089236861184 |
| 3 | -29.98419545462147 | -20.656194681587557 | -6.782608085493223 | 0.9393137990220466 |
| 4 | -26.398980868598375 | -21.326376034149895 | -13.478648954242942 | -0.688328604169324 |
| 5 | -25.211948032063084 | -23.175481305342956 | -16.80498535207805 | 0.10842504676560472 |
| 6 | -39.88709082470815 | -27.785810270606127 | -10.71569076922908 | 0.727052062493216 |
| 7 | -34.73576105048531 | -22.817912967000144 | -8.128742634437494 | -0.7916963763870569 |
| 8 | -39.29915819880178 | -28.376709917662065 | -1.8194409658777353 | -0.5317967578851917 |
| 9 | -25.59576104713534 | -25.263634971808226 | -10.132243337711985 | 0.18150837066666048 |
| 10 | -36.07783946658932 | -18.02855044451871 | -13.068053766947019 | -0.9985757018290943 |
| 11 | -31.74396992590819 | -23.449109197608358 | -2.460262579232918 | 0.7990221973996057 |
| 12 | -38.818770011919256 | -22.327651941235295 | -22.944583228712624 | 0.4746375231928559 |
| 13 | -32.82077768062364 | -17.134477571023673 | -21.772811175283096 | -0.4900775794837112 |
| 14 | -30.400201190056915 | -18.636233571472065 | -18.567601058254592 | 0.34821280337454374 |
| 15 | -37.43184843454623 | -20.4695435165393 | -22.206065865922973 | -0.6748820516763837 |
| 16 | -33.25801364400164 | -24.47955610443804 | -19.806640451691738 | 0.5704747759389279 |
| 17 | -28.09256306160669 | -19.7619482049993 | -14.547349991861914 | -0.23171275311098538 |
| 18 | -27.170068074471352 | -25.368608603832833 | -11.844509675397777 | 0.2586117856991028 |
| 19 | -30.747896716082963 | -26.368168209455785 | -0.3556963607514625 | -0.588487148316746 |
| 20 | -27.470216284367794 | -24.143964711197057 | -24.51826611085221 | 0.0592439110223304 |
| 21 | -28.53471717317919 | -16.67803759935929 | -3.4090880819360905 | -0.9353098140538937 |
| 22 | -38.35167277031334 | -29.110295557211266 | -1.1631102525479484 | -0.3848106094725603 |
| 23 | -33.59534129521289 | -17.39332708252359 | -8.62823037904996 | 0.6496385903969242 |
| 24 | -38.075303566164216 | -16.102721391158607 | -16.271493601001797 | 0.9052006162180397 |
| 25 | -29.41599242096839 | -19.054950641189638 | -11.07503804975437 | 0.1986293134764361 |
| 26 | -36.83510315549935 | -27.439181310865084 | -5.354535364562921 | -0.02873635914040973 |
| 27 | -29.18931382421533 | -28.80683628037275 | -24.049319235054217 | -0.8447099262415746 |
| 28 | -35.37327110026198 | -19.48297004996434 | -7.18538087186074 | 0.41859168638357036 |
| 29 | -34.22076360340182 | -15.796891350326643 | -17.520477441658237 | -0.10759392115213473 |
| 30 | -32.162445234122806 | -29.556871512499367 | -19.142178300059634 | -0.18518655548867136 |
| 31 | -31.361965190864055 | -25.93441643556984 | -20.718454318927154 | -0.36842791551530396 |
| 32 | -26.863928361401182 | -15.001445037212326 | -4.151703340667915 | 0.8652775587762509 |
<!-- /interior -->

- **A1's gaps:** the closed forms' phase-1 limit (§5.1), integrated beside the full system, at the
  outputs every 60 s on [0, t_off). Each gap is relative to the limit's steady state.
- **A1-M's gaps:** J̄ over the final window, and E and F at t_end, each against its closed form
  (§5.2), relative.
- **The domain:** the largest per-residue affinity of every one-sided move that a world runs, over
  its whole trajectory, at every step.
- **Conservation, as a check on the measurement itself.** These are §4.8's conserved totals at
  t_end on every lane: the machines per pool, and the four moieties over the rows and the residues
  in transit.
  - They stay within 8.9 × 10⁻¹³ of their initial values, which is rounding. The largest is a
    polymerase pool, and the moieties stay within 4 × 10⁻¹⁴.
  - So the measurement's transcription of §4.7 conserves what the move matrix conserves.
- **Each bound** is twice the largest gap over all 50 sets, rounded up to one significant digit.

<!-- bounds -->
| Key | Value | Where the largest occurs |
| --- | --- | --- |
| `A1 n_R` | 2.5e-4 | A1, corner ΔG′°_ATP −25, E_pd −30, E_rc/RT +1, at either E_pep (n_R does not depend on it) |
| `A1 n_P` | 5.1e-4 | A1, corner −25, −30, 0, +1 |
| `A1 E_tx` | 4.4e-4 | Corner −25, −30, −25, −1 |
| `A1 E_tl` | 3.85e-4 | Corner −25, −30, −25, +1 |
| `A1-M J` | 4.6e-5 | Ribosome-limited n_R = 100, corner −40, −30, 0, −1 |
| `A1-M E` | 3.1e-5 | Polymerase-limited T = 1, corner −25, −30, −25, +1 |
| `A1-M F` | 5.1e-5 | Ribosome-limited n_R = 100, corner −40, −30, 0, −1 |
| `A1 interior` | 5.0e-4 | A1's largest gap over the 32 interior points, any readout |
| `A1-M interior` | 5.1e-5 | A1-M's largest gap over the 32 interior points. F's gap comes from the draws' drift, which barely depends on the potentials |
| `eps_A1` | 2e-3 | ε_A1: twice the largest A1 gap, rounded up |
| `eps_M` | 2e-4 | ε_M: twice the largest A1-M gap, rounded up |
| `x_max` | −5.21 | The largest per-residue affinity: ribosome-limited n_R = 1, corner −40, −30, 0, +1 (protein degradation at E_pep = 0) |
<!-- /bounds -->

**What it shows.**
- **The interior.** No interior gap exceeds half its bound: 5.0 × 10⁻⁴ against 10⁻³ in A1, and
  5.1 × 10⁻⁵ against 10⁻⁴ in A1-M. So the bounds stand by their rule. They were measured at the
  corners, both peptide values and the interior sample.
- **Peptide energies.** Both candidates for E_pep, and the range's ends, sit inside both bounds.
  The kinetic effect of E_pep reaches the closed forms only through protein degradation's
  back-term, e^(y_P).
  - In A1 it is about 6 × 10⁻⁶ at Martin's value, 10⁻³ at Spirin's and 2 × 10⁻³ at E_pep = 0.
  - In the ribosome-limited worlds, at 5 mM amino acid, it reaches 5 × 10⁻³ at E_pep = 0.
- **The domain** holds everywhere with a wide margin: −5.21 against x_dom = −1. The one-sided
  laws never approach their refusal.

## 6. What the references compute

Every reference reads this sheet alone. Each is a function of the four symbols in §3.3, and of
every declared value. Two test instances are run with full trajectories: the numeric test
instance, and the same with Spirin's E_pep (§5.6).

**The readouts, per world** (exact definitions, in the units of §0):
- every row's amount n_s(t), and X's in A1;
- per pool, F_q(t). Per route, every stage's C_ρ,j(t), and E_ρ(t) = Σ_j C_ρ,j(t);
- the cumulative extents from t = 0, ∫₀ᵗ of each flux of §4.7:
  - ∫J_I_ρ, the initiations;
  - ∫S_ρ, the stage exits;
  - ∫Q_ρ, the releases;
  - ∫D_s, the degradations;
  - ∫J_C, recharging, signed;
- the residues in transit W_ρ(t);
- G(t) − G(0), and the five heat classes H_tx, H_tl, H_deg,R, H_deg,P and H_rc, in pJ (§3.4);
- the residuals of every identity in §4.8;
- A1-M's window rate J̄.

**The references:**
- **R-chain:**
  - §5.1's closed forms over phase 1, with their gap to the ODE;
  - A1's full stiff ODE over both phases. This is the judge of A1's trajectories.
- **R-account:**
  - every identity of §4.8;
  - each move's ΔG at the outputs, from §3.4's formulas;
  - each move class's heat, which is non-negative and non-decreasing;
  - G's identity.
- **R-share:**
  - the full ODE of the two-gene world and of every sweep world, polymerase- and ribosome-limited
    (R-machine needs both). This is the judge of their trajectories;
  - the engine's order is measured against it at several steps when the protocol runs (G6).
- **R-machine:** §5.2's closed forms, with their gap to R-share's ODE at t_end.
- **R-noise:** an exact stochastic simulation, in counts. A1's mean-field gap is reported and not
  judged; the control world is held to the sampling band.
  - **The worlds:**
    - A1's phase 1 over [0, 10,800 s], with the factors frozen as in §5.1's limit. The machines are
      counted, not taken as abundant;
    - the polymerase-limited world at T = 10, over its horizon. This one is a control: its system is
      linear in counts, so its mean must equal the deterministic one. Its factors are frozen at its
      own start: κ₀ = κ_tx φ_tx at N 5 mM, and k₀_R at M 0.05 mM and the trace;
  - **The counts:** the free machines, the complexes per stage, and the mRNA and protein molecules.
  - **The propensities, per second:**
    - transcription's initiation, λ f_pol. In A1, λ = λ_tx (§5.3). At T = 10, λ = 10 k_I_tx c₁ with
      A1-M's k_I_tx and u = 1;
    - translation's initiation, k_I_tl c₁ N_R f_rib;
    - a stage exit, κ₀ c_j;
    - a degradation, k₀ N.
  - **The rest:** monomer and fuel rows are not counted; their factors are frozen.
  - **The seed:** master seed 20261120. Each replicate draws from its own stream, and the references
    record how the streams are derived from it.
  - **The initial counts:** every machine free (10⁴ polymerases and 10⁶ ribosomes in A1; 100
    polymerases at T = 10), no complexes, and no mRNA or protein. The traces are below one
    molecule.
  - **The size and outputs:** 1,000 replicate cells each, with independent seeds. It reports the
    sample mean and its standard error beside the deterministic mean of the same frozen system:
    its ODE, with the machines counted, F = M − E. Outputs are every 60 s for A1 and every 30 s for
    T = 10.
  - **The deterministic mean** starts from the same zero products, not from the traces. The
    frozen system has no logarithm, so zero is admitted.
  - **The readouts:** in A1, F_pol, F_rib, E_tx, E_tl, n_R and n_P; at T = 10, F, E and n_R. All
    are in molecules.
  - **The sampling band** (declared, uncited: 4.5 SE, the 10/N floor and N = 1,000 are this sheet's
    constants). At every output and readout,
    |sample mean − deterministic mean| ≤ 4.5 SE + 10/N.
    - N = 1,000 replicates, and SE is the sample standard deviation over √N.
    - The 10/N floor keeps a readout whose replicates are all equal (all zero, early on) from being
      judged on a zero band.
    - **The false-alarm rate.** The two-sided normal tail beyond 4.5 SE is 6.8 × 10⁻⁶ per
      comparison.
    - So over each world's comparisons the family-wise rate is about 0.7 % for A1 (about 1,090
      comparisons) and 0.25 % at T = 10 (about 360).
  - **What the band judges.**
    - The T = 10 control must stay within it at every output. This is the references' own check of
      their stochastic simulation.
    - A1's mean-field gap is reported against the band. A gap outside it is a finding about the
      deterministic approximation, reported and not judged (§7, item 2).

**The tolerances the references must reach.**
- **ODE trajectories.** A second solve, with tolerances 100 times tighter, changes no readout by
  more than 10⁻⁹ of its scale. The scale is the readout's largest magnitude over the horizon.
- **Closed forms:** evaluated to 10⁻¹² relative.
- **Identities:** residuals within 10⁻¹² of each identity's scale.
  - The machines: M_q. The moieties: their totals, with the residues in transit counted.
  - The residues, per route: r ∫S at t_end. A product: n(0) + ∫Q at t_end.
  - G's identity: ΣH = H_tx + H_tl + H_deg,R + H_deg,P + H_rc at t_end. G(0) scales nothing, since
    it depends on the moiety references that §3.1 cancels.
  - Each accumulating scale is taken at t_end, not at t. Early on, r ∫S, ∫Q and ΣH are near zero
    while rounding is not.
  - **The solve they are judged on.** The 10⁻¹² tolerances are judged on a solve that conserves
    linear invariants to rounding, that is, an explicit Runge–Kutta solve. On an implicit solve,
    each identity's tolerance is tied to the solve's nonlinear tolerance, which is stated beside
    it.
- **The limits:** the gap is reported, against ε_A1 and ε_M (§5.1, §5.2).
- **R-noise:** the sampling band above. The T = 10 control is held to it; A1's gap is reported
  against it.

## 7. What A does not claim

Registered with A's protocol (GENE_REGULATION §7.9), so that no reader takes these as tested:
1. **No biological claim.** Every judged item is numerical, against exact references. No dataset is
   compared, since none passes (GENE_REGULATION §4.1).
2. **Means only.** No distribution, noise or burst is judged. R-noise's mean-field gap is reported,
   not judged.
3. **Open loop only.**
   - No feedback and no cascade: no product regulates any gene.
   - Occupancy is a given Hill factor.
   - No transcription factor is sequestered.
4. **No machine physics beyond capacity.**
   - There is no inactivation (the cell-free stall of GENE_REGULATION §4.1).
   - There is no traffic or queuing on a template, and there are no polysomes.
   - There is no premature termination: a complex on a degraded mRNA finishes its chain.
   - There is no proofreading beyond the declared stoichiometry.
5. **No processing.** Splicing, capping, export and folding are not modelled. A delay for any of
   them would be a declared stage, and labelled.
6. **No growth, dilution or division.**
7. **No organism.** Rates, lengths and copy numbers are declared, or cited as orders of magnitude.
   Nothing is claimed for any species.
8. **The lumps and reductions,** each declared (§1.3, §2, §4):
   - one NTP row, one NMP row and one amino-acid row;
   - no GTP row: GTP is counted as ATP;
   - AMP folded by adenylate kinase, and PPi hydrolysed at once;
   - degradation draws no fuel, and initiation draws none;
   - a chain's ends (the 5′ triphosphate and the terminal charges) are not counted;
   - the polymers bind no Mg²⁺.

   There is no claim per nucleotide, amino acid or tRNA.
9. **Charge.**
   - The neutral reduction claims no electrical or pH effect of expression.
   - The charged form claims no Mg²⁺ or pH dependence of elongation beyond its declared kinetics.
10. **A2 is development.** It makes no claim on FR-7's loop, on Vm or on FR-8's timescales.
11. **No gene-network layer.** No regulatory network is judged, and D218's door is not exercised.

## 8. Sources

**Read for this sheet on 20 November 2026,** through Europe PMC's records, BioNumbers and a
summariser of the pages. The publisher pages were not opened.

- **Dickson KS, Burns CM, Richardson JP (2000).** Determination of the free-energy change for repair
  of a DNA phosphodiester bond. *J Biol Chem* 275(21):15828–15831, doi:10.1074/jbc.M910044199.
  CC BY, per Europe PMC's record.
  - Read: the abstract, in Europe PMC's record, through a summariser.
  - From the T4 DNA ligase equilibrium, K_eq = 3.89 × 10⁴ M at 25 °C and pH 7, so ΔG°′ = −6.3
    kcal/mol for ligation.
  - The hydrolysis of a DNA phosphodiester bond is −5.3 kcal/mol. The source obtains it by
    subtracting "the known energy contribution" of ATP → AMP + PPi, whose value the abstract does
    not give.
- **Lawson JW, Veech RL (1979).** Effects of pH and free Mg²⁺ on the Keq of the creatine kinase
  reaction and other phosphate hydrolyses and phosphate transfer reactions. *J Biol Chem*
  254(14):6528–6537, doi:10.1016/s0021-9258(18)50400-2. CC BY, per Europe PMC's record.
  - Read: the abstract, through a summariser.
  - The myokinase reaction is written 2 ΣADP ⇌ ΣAMP + ΣATP, on totals.
  - K_obs is 0.391 at free Mg²⁺ = 0 and 1.05 at 1 mM, at 38 °C, pH 7.0 and ionic strength 0.25.
- **Martin RB (1998).** Free energies and equilibria of peptide bond hydrolysis and formation.
  *Biopolymers* 45:351–353.
  - Not read. Its Table I's overall free energy of hydrolysis of glycylglycine, −3.6 kcal/mol, was
    read through BioNumbers entry 114386, which states no temperature or pH.
- **Spirin AS (1999).** *Ribosomes*, p. 198.
  - Not read. About −0.5 kcal/mol for a peptide bond in a polypeptide of infinite length, read
    through BioNumbers entry 109649.
  - Used in §5.6's measurement as one of its potential sets, and named as the alternative for the
    registration's E_pep (§3.3).
- **Wiseman RW et al. (2023).** Creatine kinase equilibration and ΔG_ATP over an extended range of
  physiological conditions. *Int J Mol Sci* 24(17):13244, doi:10.3390/ijms241713244. CC BY 4.0.
  - Read: through a summariser of its PMC page.
  - ATP hydrolysis is −32 kJ/mol at pH 7, pMg 3 and 37 °C, which it attributes to Lawson and Veech.
  - Used for the test instance and the range only.
- **Rates as orders of magnitude:** GENE_REGULATION §1.1's table (Bremer and Dennis, and Dennis et
  al., through BioNumbers).

**Named from memory, not read:**
- Alberty's transformed potentials (Alberty, *Thermodynamics of Biochemical Reactions*, 2003);
- the mean velocity of a biased walk of elementary steps;
- the linear chain trick (MacDonald 1978, as FR-7's producer cites it).

## 9. Amendment R: a release step with two fates (FR-38; D284)

*Proposed 22 November 2026 by the gene-regulation lane, for the tag before any code. It amends
this sheet (tag `gr1-sheet-2026-11-20b`) without changing §0–§8. A chain that does not declare it
keeps §4.3 bit for bit.*

**What it adds.** A completed chain need not join its product row at once. It may wait in a hold
that its producer owns, and then leave at first order into one of two fate rows, a durable one and a
short-lived one, each with its own loss. This is FR-38's request (a user's, 22 November 2026, with a
reference package that states no licence; nothing of it is copied here).

### 9.1 The hold, its classes and the fate rows

- **Opt-in, per chain ρ.** A `release` block on the chain declares §9 for it. Without one, §4.3
  stands.
- **The hold.** H_ρ,k (fmol) is the amount of complete chains of ρ held in class k, for k = 1, …,
  K_ρ. K_ρ = 1 by default. A held chain is complete: L_ρ residues, and no concentration term
  (§9.5). It is the producer's own pool, like the complexes, which no other mechanism reads.
- **The fate rows.** Each class k of each chain has two rows of the model, F^d_ρ,k (durable) and
  F^s_ρ,k (short-lived). Each is one molecule of L_ρ residues of the product's chemistry, with
  the product's standard potential (μ°_F = μ°_prod) and its moiety weights. They are rows: other
  mechanisms may read them, and §4.4's degradation acts on each with its own rate.
- **One producer per fate row** (version 1; question d). A fate row is written by one chain only. A
  second chain naming it is refused. Shared fate rows would need producer labels on FR-42's shares
  (D296: each chain a label source, its own schedule naming its producer's label; erratum D) or
  the host-side cohort of §9.8, which apportions a shared pool only under first-order,
  age-independent loss.
- **The class axis and the label switch** (question e).
  - A declared class schedule ψ_ρ(t) ∈ {1, …, K_ρ}, piecewise constant on the clock's grid
    (D283), labels the molecules at one of two transitions, `label_at`:
    - at **completion**: a chain completing at t enters H_ρ,ψ(t), and keeps its class through
      release, into F^f_ρ,ψ;
    - at **release**: the hold has one class, and a molecule released at t enters F^f_ρ,ψ(t).
  - With K_ρ = 1 no schedule is declared, and nothing is labelled.

### 9.2 The release law

  Q^d_ρ,k = p_ρ(t) H_ρ,k / τ_ρ,   Q^s_ρ,k = (1 − p_ρ(t)) H_ρ,k / τ_ρ   (fmol/s)

- **τ_ρ > 0** is the mean dwell in the hold (declared; the exit half-life is τ ln 2).
- **p_ρ(t) ∈ [0, 1]** is the durable fraction, evaluated at release (§9.4).
- **No affinity factor.** The hold's exit carries none, as §4.3's release carries none. Its free
  energy (§9.5) is booked, and its one-sidedness is held by the domain (§9.6).
- **At p = 0 or 1** one route has a zero rate. It moves nothing, and books nothing.
- **The fates' losses** are §4.4's law, per fate row f with its own rate k_f:
  J^D_f = k_f n_f (1 − e^(y_f)), with y_f = ΔG_deg,f/(L_ρ RT), which returns L_ρ monomers.

### 9.3 The machine, a declared option per chain (question a)

- **`returned`** (the default, §4.3's physics: the machine leaves at termination). The machine
  returns at completion, J_ρ,m. The hold holds no machine.
- **`held`.** The machine stays engaged through the hold and returns at release. The hold is then a
  terminal stage that adds no residues, left at rate 1/τ_ρ. The engaged machines are
  E_ρ = Σ_j C_ρ,j + Σ_k H_ρ,k, and they return at Σ_f Q^f_ρ,k.
- **Initial occupancy.** H_ρ,k(0) may be declared, in copies (the 80-chain case). With `held`, the
  pool's free machines start at F_q(0) = M_q − Σ_(ρ on q) Σ_k H_ρ,k(0), which must be ≥ 0, or the
  definition is refused. With `returned`, F_q(0) = M_q.

### 9.4 The durable fraction p

One of three sources, named in the declaration and stamped in the run's record:
1. **A constant** p ∈ [0, 1].
2. **A schedule** per chain in `polymerisation_controls`, piecewise constant on the clock's grid
   (D283's same-instant predicate).
3. **A B1′ route** onto the chain's routable `release_fraction`: p = p_max u(t), with p_max ≤ 1 the
   scheduled value and u ∈ [b, 1] a coupling's factor on an engine state.
   - **Evaluation.** u is evaluated at the half-step's start, as B1′'s routes are. Where the
     release moves u's own source (a fate row as the source, say), u is evaluated at the
     half-step's midpoint instead, which keeps second order (B1′'s midpoint rule, e27849be).
   - **Record.** The composite records the factors applied at each step.

No host callable supplies p.

### 9.5 Free energy and heat

- **G gains the held chains' standard term:** Σ_ρ,k L_ρ μ°_ρ,res H_ρ,k. It is booked like §3.4's
  residues in transit, with no concentration term.
- **Each move's ΔG.**
  - **Completion** into the hold books r_ρ ΔG_ρ: its residue moves only.
  - **Release** into fate f books ΔG^rel_f = μ_F − L_ρ μ°_ρ,res = RT ln(c_F/c°). This is §3.4's
    release term, now at the hold's exit and split across the fate rows by their own
    concentrations.
  - **A fate's loss** books §3.4's ΔG_deg with its own row.
- **The heat classes.** H_rel,ρ,f = ∫ Q^f (−ΔG^rel_f) dt joins §3.4's classes. A chain with §9 has
  no release term in its H_tx or H_tl.
- **No work, no new energy object.** The release adds no work term and no new energy field. The
  identity G(t) − G(0) + Σ H = 0 holds with every class ≥ 0 inside the domain (§9.6).
  - This is the contrast with the requester's replay, whose driven `mass_action` books the release's
    and the loss's ΔG as work. There, a move into a fuller pool is booked as positive work, which
    the dissipation check does not see.

### 9.6 The domain

- **One-sided release.** At a release in use, c_F ≤ c° = 1 M, so ΔG^rel_f ≤ 0. A state outside it
  is refused, never repaired (§3.5).
- **The fates' losses** are one-sided as §3.5's degradations are: y_f ≤ x_dom.
- **p** lies in [0, 1], τ > 0, and every rate is ≥ 0. Each is checked at the definition, or at run
  time for a routed p.

### 9.7 The equations of motion and the identities

Per chain ρ with §9 and K_ρ = 1, beside §4.7's columns. Q_ρ = J_ρ,m is now the completions:
- dH_ρ/dt = Q_ρ − Q^d_ρ − Q^s_ρ;
- dn_F^f/dt = Q^f_ρ − D_F^f, for f = d, s;
- the machine: with `returned`, dF_q/dt gains +Q_ρ as in §4.7; with `held`, it gains Q^d + Q^s
  instead;
- the residues in transit: W_ρ loses L_ρ at Q_ρ, as in §4.8, and the hold holds L_ρ per molecule.

**The counters**, each cumulative from t = 0:
- arrivals A_ρ = ∫Q_ρ (the existing int_Q);
- the hold H_ρ,k;
- the release into each fate ∫Q^f_ρ,k;
- each fate row's loss ∫D_F^f (the existing int_D, per fate row).

**The identities:**
- **The hold:** H_ρ(0) + A_ρ(t) = H_ρ(t) + Σ_f ∫Q^f_ρ(t).
- **Each fate row,** with one producer: n_F^f(t) = n_F^f(0) + ∫Q^f_ρ(t) − ∫D_F^f(t).
- **Per producer:** initial + arrivals = attached + surviving + lost, exactly:
  H_ρ(0) + A_ρ(t) = H_ρ(t) + Σ_f [n_F^f(t) − n_F^f(0)] + Σ_f ∫D_F^f(t).
- **Machines:** §4.8's, with the hold among the engaged where the machine is `held`.
- **Moieties and energy:** §4.8's, with the hold's residues counted in the residue identity and
  its standard term in G.

**Restart.** The hold, its classes and every counter are state, so a checkpoint and resume carry
them bit for bit. Replacement waits for the requester's answer (question c).

### 9.8 The release-window cohort, by two routes

Of the molecules released into fate f during [t1, t2], the amount still present at ts ≥ t2:
1. **Shares** (FR-42's neutral arrival-time labels, D289; erratum C). The label marks the
   release. FR-42's label owner labels each fate row, its base label first, and its arrival
   schedule names the window's label during [t1, t2) and the base otherwise.
   - A release joins the label in force at the start of its step.
   - The cohort is F^f_ρ(ts) s^f_w(ts), the fate row times its window label's share.
   - **No blank.** A cohort's share starts at exactly zero. The fate's loss is computed once on
     the physical row and shared by its labels, so there is no class-row departure (erratum B).
   - **Its error is the share update's split.** It is exact for a constant per-molecule loss rate
     and constant arrivals within a half-step. Otherwise it errs by (a k′ − a′ k) h³/12 per
     half-step h, which is second order over a run. In R1 the arrivals into fate f decay with the
     hold (a′ = −a/τ) at a nearly constant loss rate k_f. So route 1 lies within k_f h²/(12 τ),
     relative, of the cohort the update would give exactly.
2. **Host-side.** `validation/gene_regulation/cohort.py` on each fate pool's own counters, n_F^f,
   ∫Q^f and ∫D_F^f. It is exact for first-order, age-independent loss in a well-mixed pool, up to
   its grid error.

Under §9.2's laws both routes apply, and they must agree within the host-side route's grid error
plus route 1's split.

**The survival readout** (the requester's answer to questions (c) and (e)): the window's members
alive at t2, the same molecules alive at a later ts, and their ratio, undefined at a zero
denominator. Route 1 reads its cohort at both times. Route 2 computes both from the counters.

**The class rows** (§9.1's K_ρ > 1) remain for labels marked at completion, until FR-42's label
owner holds the hold's own shares (D296). Their sum departs from the unlabelled row (erratum B):
- **The factor.** A class row k of a fate with total N reads its own potential (§9.2). Its loss
  factor is therefore 1 − e^(y_f) (N/n_k)^(1/L), where e^(y_f) is the population's, not
  1 − e^(y_f).
- **At R1,** e^(y_f) ≈ 9.4 × 10⁻⁹, so the departure is at most about 10⁻⁸ relative (erratum A2).
  That is well inside the two routes' agreement bound.
- **In general** it is not small. Near the domain bound, y_f → x_dom, it reaches percent level for
  a small class.
- **Not physical for a neutral label.** The departure would be physical only for a chemically
  distinct label. For a neutral arrival-time label, as here, it is an artefact of separate rows,
  which FR-42 asks labels never to have. Erratum B retracts erratum A's "physical".

### 9.9 The release worlds

**R1, the requester's hold** (its acceptance case):
- one 1 pL cell with one chain of A1's transcription (L_R = 1200, m_tx = 8, v_tx = 50 nt/s);
- k_I = 0, so nothing completes, and H(0) = 80 copies;
- τ = 3600/ln 2 s (an exit half-life of 1 h), and p constant;
- the fates' rates k_d = ln 2/7200 s⁻¹ and k_s = ln 2/1800 s⁻¹ (half-lives of 2 h and 0.5 h);
- the fate rows start at the inventory trace;
- every other row as A1's initial state, at the numeric test instance.

It is run at four fractions, p ∈ {0, 0.25, 0.75, 1}, beside a matched blank (H(0) = 0), with
`returned`, and with `held` (M_pol = A1's 10⁴).
- **Outputs:** 0, 1,800, 3,600, 7,200 and 14,400 s.
- **The release-window cohort:** [0, 3,600 s], sampled at 3,600 and 7,200 s.

**R2, A1 with the release step:**
- A1 (§5.1), with transcription's chain declaring §9: τ = 3600/ln 2 s, p constant 0.75, and the
  fates' rates as R1;
- both machine options;
- A1's horizon and outputs.

**Addendum: R2's rows and translation, a declared choice** (the lead's ruling, 22 November 2026,
tagged before R2's code and references):
- **The fate rows, in R1 and R2.** The durable fate is A1's R. The short-lived fate is a new row
  R_s with R's chemistry: R's μ° and moiety weights (§9.1). "The inventory trace" is the sheet's
  trace c_R = 1.0 × 10⁻¹² mM, so R_s starts there, as R does.
- **The fates' losses.** deg_R takes the durable rate k_d. A new degradation deg_R_s, with deg_R's
  form and standard free energy, takes the short-lived rate k_s.
- **Translation.** Two chains, `tl` templated by R and `tl_s` templated by R_s. Each has A1's
  translation parameters (§5.1), and both share the ribosome pool and make P. The two fates are
  one chemistry, so both are translatable.
- **A development check, not an acceptance row.** Set both fates' loss rates to A1's k_R.
  - Each chain's initiation is linear in its template, so translation's initiation sees the total
    RNA, R + R_s.
  - R2's total RNA and protein then follow A1's, delayed by the hold. They approach A1's as τ
    shrinks, with either machine option.
  - They differ from A1's by the hold, by R_s's starting trace, and by each fate's own factor
    (1 − e^(y_f)) (§9.10).

<!-- release -->
| Symbol | Value | Unit | Meaning | Source |
| --- | --- | --- | --- | --- |
| `H0` | 80 | copies | R1's initial hold | The requester |
| `tau` | 5193.7 | s | 3600/ln 2: an exit half-life of 1 h | The requester |
| `p_cases` | 0, 0.25, 0.75, 1 | 1 | R1's durable fractions | The requester |
| `k_durable` | ln 2/7200 | s⁻¹ | A half-life of 2 h | The requester |
| `k_short` | ln 2/1800 | s⁻¹ | A half-life of 0.5 h | The requester |
| `t_out` | 0, 1800, 3600, 7200, 14400 | s | R1's outputs | The requester |
<!-- /release -->

### 9.10 The requester's limit, and the release worlds' distance from it

- **The limit.** The requester's numbers assume pure first-order exits and losses. At p = 0.75 and
  t = 1 h:
  - 40 held and 40 released, 30 into the durable row and 10 into the short-lived one;
  - of those, 24.852814 durable and 5.000000 short-lived still present.
- **Their closed forms,** with k_e = 1/τ:
  - hold: H(t) = H0 e^(−k_e t);
  - survivors in fate f: π_f H0 k_e (e^(−k_e t) − e^(−k_f t))/(k_f − k_e).
- **The distance of R1 and R2.**
  - **The release law** has no affinity factor (§9.2), so it sits on the limit exactly.
  - **The fates' losses** carry §4.4's factor (1 − e^(y_f)). At R1's state, at the test instance:
    - y_f ≈ −18.48 at every fate amount from the trace to 80 copies;
    - so e^(y_f) ≈ 9.4 × 10⁻⁹;
    - each loss rate is k_f (1 − 9.4 × 10⁻⁹), and each survivor sits within about 10⁻⁸ of the
      limit, relative.
  - The limit's six-decimal figures stand at that distance.
  - **The quantity compared** (erratum A, R-F2): the released molecules still present in fate f,
    the fate row minus the matched blank's (§9.8). The fate rows themselves also carry their
    starting trace, so they sit further from the limit, up to about 10⁻⁴ relative.
- **No amount or potential was chosen to reach a tolerance.** R1's amounts and potentials are A1's
  and the requester's.

### 9.11 What the amendment does not claim

1. **No biology.** τ, p and the fates' rates are declared. No dataset is compared.
2. **No release energy** beyond the residues' standard term (question b). If a retention or binding
   free energy is declared later, it is a new term of §9.5.
3. **No replacement semantics** for the hold or the fates (question c).
4. **One producer per fate row** (question d). Shared rows would need producer labels on FR-42's
   shares or §9.8's host-side route (erratum D).
5. **Neither label transition is the default reading** of the requester's "release window"
   (question e). Both are declared, and the requester names the one meant.
6. **No observation layer** here. Per-copy detection, roster denominators and two-colour statistics
   are `src/cells/assays`, built separately.
7. **R2's translation is a declared choice,** not a biological claim (§9.9's addendum): two chains,
   one per fate row, because both fates are one chemistry.

**The requester's questions,** carried to their answer:
- (a) does an attached chain keep its machine;
- (b) the release energy;
- (c) what "replacement" means for producer identity;
- (d) one gene per producer;
- (e) which transition the label switch marks.

### 9.12 Erratum A: the readings where §9 was silent

*22 November 2026, after the code-blind references (tag `gr-refs-fr38-2026-11-22`), so that the
builder and the references read one sheet before the registered comparison. It settles their two
findings, R-F1 (§9.8) and R-F2 (§9.10), in place, and the readings below.*

1. **R1's routes.** The chain at k_I = 0, its release, and the fates' two degradations: no
   recharging, translation or regulator. N, M and Pi start at A1's initial state and are moved
   only by the routes in use (the fates' losses return NMPs to M; erratum A2). §9.10's y_f ≈
   −18.48 reads M at A1's 0.05 mM.
2. **The inventory trace** is the sheet's c_R, 1.0 × 10⁻¹² mM (§9.9's addendum).
3. **The matched blank** is the same world with H(0) = 0, everything else equal.
4. **The limit's survivors** are the released molecules still present: each fate row minus the
   matched blank's (§9.10).
5. **The heat classes.** deg_R books to H_deg,R and deg_R_s to its own class, H_deg,R_s. H_rel is
   per fate. H_tl sums tl and tl_s.
6. **The engaged machines** E_tx are ΣC + ΣH under `held` and ΣC under `returned` (§9.3).
7. **The label** (as erratum C amends it). The window's label is the one in force at the start of
   each step, resolved by step index from the label owner's schedule. So a release in [t1, t2)
   joins it, and a release in the step that starts at t2 does not. R1L labels R and R_s (base,
   cohort) and has no class rows.
8. **R2's hold** starts empty, H(0) = 0. **R2's cohort** is route 2 alone; route 1 is not computed in
   R2.
9. **R1's domain** leaves out elongation, which has no complexes there: §9.6's and §3.5's bounds
   hold at the routes in use.

### 9.13 Erratum B: the label rows are not neutral labels

*22 November 2026, after FR-42 (neutral arrival-time labels; the lead's request), docs only.*

1. **Retracted:** erratum A's statement that the label rows' departure is "physical, not an
   error". It is physical only for a chemically distinct label. §9.1's class rows are meant as
   neutral arrival-time labels, and a neutral label must leave the loss, the free energy and the
   heat of its physical population unchanged (FR-42).
2. **The departure's general form** (§9.8): a class row's loss factor is 1 − e^(y_f) (N/n_k)^(1/L),
   with N the fate's total and n_k the row's amount. The bound of about 10⁻⁸ holds at R1 alone,
   where e^(y_f) ≈ 9.4 × 10⁻⁹.
3. **Route 1 is provisional, pending FR-42.** Its blank subtraction is exact only for a loss linear
   in the amount. The user decides whether FR-38's label rows are replaced under FR-42 before the
   registered comparison.
4. **Route 2 stands.** cohort.py reads the run's own per-molecule loss, which is FR-42's method on
   the host.

### 9.14 Erratum C: route 1 on shares

*22 November 2026, after FR-42's stage 1 (D289) and the user's decision that FR-42's shares replace
the class rows (D288). Docs only, before the code that builds on it.*

1. **Route 1 moves to shares** (§9.8). R1L's fate rows carry FR-42's labels, with the window
   marked at release, in place of the class rows R_c2 and R_s_c2. The cohort is the fate row times
   its window label's share, with no blank.
2. **Reading 7** (§9.12) reads the window's label from the label owner's schedule at the start of
   each step.
3. **R1L's blank is dropped.** The matched blank stays for the survivors (§9.10; §9.12, reading 4).
4. **Route 1 is second order.** Its error is the share update's split (§9.8), not the
   operator's third-order step. In R1 the split is k_f h²/(12 τ), relative: below 6.2 × 10⁻⁹ at
   R1's step of 2 s. FR-38's registered comparison declares p = 2 for route 1.
5. **The requester's answer to (e) marks the window at release** (§9.11, question e).
   - A molecule that detaches from its template during [t0, t1) belongs to the cohort, even if it
     finished transcription before t0.
   - One released exactly at t1 belongs to the next window.
   - Labelling at completion (§9.1) stays declared, on the class axis, until the label owner holds
     the hold's own shares (D296).
6. **The survival readout** (§9.8) is the requester's answer to (c) and (e).
7. **A limit:** a labelled species carries at most the label owner's MAX_LABELS labels. So
   producer identity crossed with the window labels must fit within it.
8. **Route 2 stands** (erratum B).

### 9.15 Erratum D: producer labels on shares, not label families

*22 November 2026, after D300 retired D1's own-potential label families. Docs only.*

1. **§9.1 and §9.11 (item 4)** named D1's label families per producer as one way to share a fate
   row between producers. D1's families are retired (D300): each family row carried its own
   potential, so a label changed the physics (erratum B's departure, in another form).
2. **Producer labels on FR-42's shares replace them** (D296). Each chain is a label source, and the
   label owner's schedule may name a chain, so a producer's label (its cell, occupant generation
   and chain, crossed with the window) marks its material without changing the physics.
3. **One producer per fate row stays version 1's rule.** A second chain naming a fate row is still
   refused; sharing one is a later extension, now on shares.

### 9.16 Amendment S: the producer across replacement (FR-38's step 4; D296, D301)

*Proposed 22 November 2026 by the gene-regulation lane, for the tag before any code. It answers
question (c) with the requester's clarification of 22 November (docs/FEATURE_REQUESTS.md, FR-38),
replaces §9.7's "Replacement waits" and §9.11's item 3, and lifts D301's temporary refusal. A
definition without a replacement keeps §0–§9.15 bit for bit.*

1. **Scope.**
   - `templated_polymerisation@1` composes with `scheduled_cell_replacement@1`, whose events
     replace a slot's occupant by a newcomer from an isolated template.
   - Refused in version 1, each at the definition:
     - a donor copy into a slot that holds a pool of this operator, or from one (D152 defers its
       own donor copies to version 1.1);
     - `scheduled_cell_replacement@2`, as the declarations already refuse it: water provides the
       volumes this operator reads as declared.
   - A replaced slot's chains, releases, degradations and transfers are those whose cell it is. A
     pool and its chains share one cell, so an occupant takes its whole gene unit with it.
2. **The event.** At the start of the step leaving t_e, the step in which replacement@1 swaps the
   slot's rows, this operator's own event part acts on every replaced slot c:
   - **The chains in progress leave.** Every chain ρ at c sets C_ρ,j → 0. Its counters gain the
     chains removed Σ_j C_ρ,j and the residues removed W_ρ = r_ρ Σ_j (j − 1) C_ρ,j (§1.2).
   - **The hold leaves.** Every release of such a chain sets H_ρ → 0, and its hold-removed counter
     gains H_ρ.
   - **The newcomer's machines are all free.** Every pool q at c sets F_q → M_q. Machines carry no
     free energy (§1.2), so this books nothing.
   - **The free energy leaving with them** is μ°_ρ,res (W_ρ + L_ρ H_ρ). It is booked in a removal
     counter of its own, not as heat.
   - **The event reads only its own state and controls:** the replacements due at each slot,
     known from replacement@1's events at the definition. So it does not depend on the order of
     the two events in the operator list.
   - **The rows are replacement@1's.** It removes the occupant's amounts and supplies the
     template's (`replacement_removed_fmol`, `replacement_supplied_fmol`), with their chemical and
     capacitor free energy (`replacement_free_energy_pJ`). The rows' standard term
     Σ_s μ°'_s Δn_s at the swap is booked by neither operator. D152's owned standard term has the
     same gap, since its operator has no event part either. The engine's energy ledger closes all
     the same, because each owned standard term is an accumulator of its operator's own moves.
     Item 5 states the account with the swap computed from replacement@1's records.
3. **Generations and counters.**
   - A slot's occupants are its generations: the founder g = 0, then each newcomer g + 1,
     replacement@1's `generation`. A producer is (cell, generation, chain), preserved across
     restart and cell reordering, as IDs.
   - Every counter of §4.7 and §9.7 stays cumulative from t = 0: initiations, stage exits,
     arrivals A_ρ = ∫Q_ρ, releases ∫Q^f_ρ, each degradation's ∫D and each transfer's extent. Removal
     is counted apart from degradation, by the counters of item 2.
   - **The newcomer's counters start at zero.** Per chain, release, degradation and transfer of a
     replaced slot, the operator holds each cumulative counter's value at the current generation's
     birth (0 for the founder). At each event it records the departing generation's own totals,
     the counter at its death minus that birth value, and the counter's value becomes the
     newcomer's birth value. The newcomer's own counters are the cumulative counters minus it.
   - State holds only the latest departed generation's totals. An earlier generation's totals are
     in the records only where an output follows its death before the slot's next event; the
     definition does not require one (a declared limit of version 1).
4. **The identities across events.** Each holds at every step; the removal terms are cumulative
   from t = 0.
   - **Machines:** F_q + engaged − M_q = 0, as in §9.7. After an event every machine at c is free.
   - **Residues in transit, per chain:** r_ρ ∫S_ρ = W_ρ + L_ρ A_ρ + W^rem_ρ.
   - **The hold, per release:** H_ρ(0) + A_ρ = H_ρ + Σ_f ∫Q^f_ρ + H^rem_ρ.
   - **Per producer,** for generation g of chain ρ between its birth t_b and its death t_d, with
     one producer per fate row (§9.11, item 4) and no other mover of it (a transport, FR-42's
     stage 2, adds its own term):
     H_ρ(t_b) + A_g = H^rem_g + Σ_f [R^f_g + ∫_{t_b}^{t_d} D_F^f], where
     - A_g is the arrivals of its life, and H_ρ(t_b) = 0 for a newcomer;
     - H^rem_g is its hold at t_d, which the event removes;
     - R^f_g = n_F^f(t_d) − n_F^f(t_b) is the net RNA it added to fate row f. Replacement@1 removes
       n_F^f(t_d) at the event and supplies the template's n_F^f(t_b) of the next generation;
     - so initial plus arrivals equals attached, surviving, lost and removed RNA, with removal
       booked to the departing generation and apart from degradation.

     A living generation's identity is §9.7's, from t_b.
   - **Moieties** (§1.4, §4.8): each total over the rows, the residues in transit and the hold
     changes only at events, by what they supply less what they remove. The rows' parts are
     replacement@1's supplied and removed records. The transit's and the hold's are item 2's
     removal counters: W^rem_ρ residues and L_ρ H^rem_ρ residues.
5. **The energy account.**
   G(t) − G(0) + Σ H + Σ_events (G^out − G^in) = 0, where:
   - G^out is the departing occupant's G within §3.4's scope: its rows' terms at removal, from
     replacement@1's removed amounts, plus item 2's transit and hold terms, from this operator's
     removal counter;
   - G^in is the newcomer's, its template's rows at supply. Its transit and hold are empty.

   Each class of Σ H stays non-negative and non-decreasing inside the domain (§3.5, §9.6). The event
   books no heat.
6. **The newcomer's rates (the occupant rule, D244).**
   - An optional `templates` key gives them: {template_id, rates: {route ID: value}} for a
     replacement template whose newcomers fill a slot of this operator. A route here is a chain's
     k_I, a degradation's k, a transfer's capacity, or a scheduled release's p.
   - Each route of a replaced slot takes its template's value from the newcomer's birth.
   - Refused at the definition:
     - a route of a replaced slot without its template's value;
     - a template value for no route its newcomers take;
     - a template that is not a replacement template;
     - a schedule change of a replaced slot's route after its founder's death. In version 1 a
       newcomer's values are its template's, constant through its life.
   - The gene's copies T, the chains' structure and the pools' machines M are declared per slot,
     so the newcomer has the founder's.
   - A definition without the key keeps its declaration, to_dict and fingerprint byte for byte.
7. **Labels (D296; the label owner's side).**
   - The producer's label is a label source's schedule, the chain's, naming (cell, generation,
     chain) from each generation's birth.
   - At the event the label owner gives the replaced slot's labelled rows and this operator's hold
     pools the label in force there, the newcomer's. The departing material leaves with its shares.
   - **Extracellular RNA is not admitted in version 1.** `check_writers` refuses every other
     mover of a listed row: another author such as exchange, and an in-step mover such as a face.
     So no fate row leaves its cell, and the requester's retention of a producer's label outside
     the cell needs a transport door that this amendment does not define.
   - Labels change no physics.
8. **Restart.** Item 2's and item 3's counters, and the replacements applied per slot, are state.
   So a checkpoint and resume carry them bit for bit, and the controls come from the definition.
9. **Static.** Without replacement@1 in the composition, or with no event on a slot of this
   operator, every new field is zero-size. The event part then returns its state unchanged with no
   validity term, so no program gains an equation. Under D148's case 2 (D296), the proof is the
   programs check and `validation/gene_regulation/optin_check.py` before and after, with every
   physical field bitwise.
10. **What it does not claim.**
    - **No biology** in the departure: that an occupant's chains in progress and its hold leave
      with it is the requester's reading of replacement, declared. A newcomer that inherits a
      chain is not modelled.
    - **No donor copies** (item 1), and **no `scheduled_cell_replacement@2`**.
    - **No standard term for the rows' swap** in the engine's bookings (item 2). It is a gap
      shared with D152 on a desk reading (its docstring and its having no event part, no run),
      reported to the lead.
    - **No extracellular retention** (item 7).

### 9.17 Amendment T: extracellular retention, options and the choice (FR-38; D284, D303)

*Proposed 22 November 2026 by the gene-regulation lane, for the tag before any code. The lead's
review approved option (a) with two changes, folded in: only a driven export in version 1
(§9.17.2), and several producers admitted into one node row (§9.17.3). The requester asks that "RNA retained in an extracellular compartment keeps its original
producer ID", and D284 is full scope, so D303 restores it to FR-38. When tagged, this amendment
supersedes amendment S's extracellular bullet (§9.16, item 7) and its non-claim (§9.16, item 10). A
definition without an export keeps §0–§9.16 bit for bit.*

**Where Cells stands.** `check_writers` makes this operator the one writer of its listed rows:
- it refuses another author of one (exchange and turnover declare their species);
- it refuses a D152 reaction that writes one;
- it refuses an in-step mover of one at a cell (a face, a membrane, junction or channel route, a
  kind, an in-step process).

A listed row also has zero membrane, junction and channel permeability (species_common). So
today no admitted path carries a fate row out of its cell.

#### 9.17.1 The options: which mover carries a fate row out of its cell

**(a) This operator owns the export (recommended).**
- It gains `exports`: each a fate row, or a product, of a chain at a patch's inside cell, moved
  across that patch into its outside node, a finite extracellular node.
- It gains `outside_degradations`: the exported row's loss at that node, to its monomers at the
  node, which is the retention's lifetime.
- It stays the one writer, now at the node too (refusals, below).
- It reports each export to FR-42's label owner as a transfer from (row, cell) to (row, node),
  as exchange does at stage 3, so the shares ride with the material.
- **Files and owners.** All in the gene-regulation lane:
  - this sheet;
  - src/cells/operators/templated_polymerisation.py;
  - validation/gene_regulation/ (worlds, engine_run's export, cohort, release_check, optin_check);
  - tests/unit/test_templated_polymerisation.py and test_gene_regulation_compare.py;
  - the lane's rules in validation/tissue/composition_matrix.py.

  On FR-42's stack (core-pass-kinds-26), the label owner (species_labels.py, the kinds owner)
  already consumes a split reporter's transfers, from exchange's stage-3 report. So it needs only
  a review, not a change. No other owner's src changes.

**(b1) A door for exchange.** check_writers would admit `scheduled_species_exchange@1`'s export
routes of a fate row as a second mover. The per-producer identity would read exchange's booked
one-way flows (`exchange_moved_fmol` per route).
- **Files and owners:**
  - this operator's check_writers and the matrix (the gene-regulation lane);
  - exchange's identity of the row, agreed through the species registry (one authority per
    species; the registry's owner);
  - exchange itself, unchanged but reviewed by its owner (D150's operator).
- **The retention's loss needs a second door.** Exchange has no loss, so the loss at the node
  would be either turnover's clearance, another author admitted the same way, or this operator's
  outside degradation.
- **The energy is driven work.** Exchange books each move's exact ΔG as signed work, with no heat
  (its docstring: a first-order export can run uphill). An export into a retaining node that
  fills past the cell's concentration then books positive work that nothing pays for. That is
  the contrast §9.5 draws with the requester's replay.

**(b2) A door for a face.** An in-step face between the cell and the node would carry the row, as
FR-42's stage 2 reports for uncharged faces (F2's exact heat applies).
- **Files and owners:**
  - this operator's check_writers (the gene-regulation lane);
  - the @3 owner's faces and their per-species transfer records, which the identity would read;
  - the registry's moved_in_step.
- **Physically unsuitable.** A face is free diffusion between nodes. A cell's RNA crossing its
  membrane is not diffusion through an open face, and the face would also carry every other
  diffusible row of the cell.

**The recommendation is (a).**
- It keeps the one-writer rule, so every identity of §4.8, §9.7 and §9.16 stays exact, with the
  export's counter added.
- Its energy is heat by the operator's own law form, with no unpaid work.
- It needs no change in another owner's src.
- (b1) reuses exchange, but brings driven work, a second door for the loss and two more owners'
  reviews.
- (b2) is the wrong physics for RNA.

#### 9.17.2 The export law, under (a)

Per export e of row F from cell c into node o, across patch π (inside c, outside o):

J_E = k_E n_F,c φ_E (1 − e^(x_E)),  x_E = [μ_F,o − μ_F,c + Σ_k ν_k μ_k,c] / RT.

- **The coupling** ν is declared data: the cell's rows the move consumes and releases per molecule
  exported, for example one ATP to ADP and Pi for a vesicular export. In version 1 it is non-empty:
  only a driven export is admitted (the lead's choice (i), 22 November 2026). RNA export from cells
  is generally active, vesicular or transporter-driven.
- **φ_E** is the product, over the consumed coupling rows, of c/(K + c), with K declared for each.
- This is §4's one-sided form, as for the stage exits and the degradations: at an export in use,
  x_E ≤ X_DOM = −1, and a state outside it is refused, never repaired (§3.5). A driven export
  stays far inside that domain while the coupling's affinity pays for the gradient.
- **Why the passive form is refused.** With an empty coupling, x_E = ln(c_F,o / c_F,c), so the
  domain refuses a node filled past c_F,c / e. That is exactly the requester's chase: the cell's
  RNA decays while the retained RNA persists, so c_F,o / c_F,c rises through 1/e and the run would
  be refused mid-chase, where the replacement test lives. **(ii), a follow-on on request:** the
  passive form's own two-sided law, export and re-import, with both one-way moves reported to the
  labels.
- **Energy:** heat H_E = J_E (−x_E RT) ≥ 0, booked exactly from the state by the half-step's
  divided-difference potentials, as every route's is (§3.4). F's standard term cancels between
  the two nodes; the coupling's rows carry theirs, booked as a transfer's are. No work.
- **The rate k_E** is scheduled in `polymerisation_controls` under the export's ID. dt k_E ≤ 1 is
  checked at the definition. Under amendment S, a replaced slot's export takes its newcomer's k_E
  from the template (§9.16, item 6).
- **The outside degradation** is §4.4's law at node o, with o's volume and its rows. Its monomers
  stay at o (an extracellular RNase's products). G gains o's rows: §3.4's G extends over the
  nodes the operator writes.

#### 9.17.3 The per-producer identity across export

For generation g of chain ρ, with one producer per fate row (§9.11, item 4), and each export from
a fate row of ρ (in what follows f runs over the fate rows and e over their exports):

H_ρ(t_b) + A_g = H^rem_g + Σ_f [R^f_g + ∫_{t_b}^{t_d} D_F^f] + Σ_e ∫_{t_b}^{t_d} E_e.

The exports over its life are counted from §9.16's birth values, with the export counters among
them. At node o, with this operator its one writer:

n_o(t) = n_o(0) + Σ_e ∫_0^t E_e − ∫_0^t D_o.

This holds over every generation and every producer exporting into o. Replacement@1 swaps cells
only, so an event leaves o untouched. **Exported RNA survives its producer's replacement, retained
with its label.**

**Several producers may share one node row** (the lead's review, 22 November 2026). A shared
extracellular space is the natural tissue case, and producer labels on FR-42's shares exist so that
one row can hold several producers' RNA. Each export route belongs to one chain, so its counter ∫E_e
is that chain's exports, and §9.16's birth values split it by generation. Nothing in the node's
balance or the identities above needs one producer per node row; the fate rows keep §9.11's one
producer each.

#### 9.17.4 The label, on FR-42's shares (D289, D296)

- The label owner labels a species at every node, so the node's row carries the fate row's labels.
- Each export is reported as a transfer that carries the source's shares (cell c's) into o, and
  the outside loss as o's out.
- The producer's label (cell, generation, chain) set at the chain's completions (§9.16, item 7)
  therefore rides into o.
- At replacement the label owner gives the replaced cell's rows the newcomer label. Node o is not
  replaced, so the departed generation's label stays on its exported RNA.

#### 9.17.5 Readouts, each by two routes that must agree

1. **Extracellular RNA by producer.**
   - Route 1: n_o times the producer's share at o.
   - Route 2, host-side: each producer's exports, its chain's export counter over each
     generation's life, carried by o's own per-molecule loss, ∫D_o over n_o from the counters
     (cohort.py's form, exact for first-order, age-independent loss in a well-mixed node, up to its
     grid error). The node's loss is shared by every producer's RNA at one per-molecule rate.
   - **A row with two producers into one node:** two cells, each with its own chain and fate row
     of the same species, exporting into one finite node. Each producer's RNA there, by both
     routes, and their sum the node's row.
2. **The release-marked cohort's survival at o.**
   - Route 1: n_o times the window's share. A molecule released in [t1, t2) keeps that label
     through export.
   - Route 2: two pools in series. The cohort in the fate row leaves by loss and export at the
     run's own per-molecule rates, and its exported part then decays at o's.
   - The survival readout of §9.8 applies at o: the members alive at t2, the same molecules alive
     at a later ts, and their ratio, undefined at a zero denominator.
3. **RNA at o from a generation replaced later.**
   - Route 1: the departed generation's producer share at o after its death.
   - Route 2: route 2 of readout 1, restricted to that generation's window [t_b, t_d).

#### 9.17.6 Refusals

At the definition:
- an export of a row that is no fate row or product of a chain at the patch's inside cell;
- a patch whose outside node is a held bath (secretion into it is clearance), or is not finite;
- any other writer or mover of the exported row at its node: an author such as exchange or
  turnover, a D152 reaction, or an in-step mover such as a face or a kind (retention is the
  one-writer rule extended to the node);
- an export whose coupling is empty (the passive form, §9.17.2: follow-on (ii));
- a coupling row that is not a listed row of the cell, or a consumed one without its K;
- dt k_E > 1, and an outside degradation's dt k > 1;
- a provider of the volumes, as today (CONFLICTS_VIEW).

At run time: x_E > X_DOM at an export in use, a non-positive amount, a non-finite value.

#### 9.17.7 Bitwise (D148's case 2)

- Without `exports` and `outside_degradations`, every new array is zero-size, and no export or
  outside computation is traced.
- The new outside accumulators are sized by the exported nodes, not by the extracellular capacity,
  so they are zero-size too.
- The proof is the programs check and optin_check's 128 definitions before and after, with every
  physical field bitwise and only the new empty fields added (its verdict learns them).
- **First probe, before any field:** the class-level declaration of the new write target (the
  nodes' amounts among ENTITY_WRITES). As the EVENT flag was probed for §9.16, it is checked
  against optin_check's definitions and programs dumps. If it moves anything for a definition
  without exports, the lead decides before the build.

#### 9.17.8 The price, in agent-days

- **(a):**
  - this amendment 0.5;
  - the export, its coupling, its heat and its domain 1.5–2;
  - the outside degradation and the nodes' accumulators and ledgers 0.75–1;
  - the label transfer 0.25;
  - the readouts' routes 1 and 2 (cohort.py's series form), with the two-producer row, 1–1.25;
  - tests, optin and the gate 0.75–1.

  In all about 4.75–6, after step 4 (§9.16) and alongside step 5.
- **(ii), on request:** the passive form's two-sided law and its re-import's reports, about
  1–1.5 more.
- **(b1):** about 4–4.75 with its owners' reviews, with driven work and a second door.
- **(b2):** about 4.5 with the @3 owner's review, and the wrong physics.

### 9.18 Erratum E: an emptied hold takes the base label, and what leaves is recorded by label

*22 November 2026, for the kinds owner's replacement event report (FR-38's step 5; D296). Docs only,
before the code that builds on it.*

1. **§9.16, item 7:** at the event the label owner gives the replaced slot's labelled rows the
   label in force there, the newcomer's, and each hold this operator empties the base label. An
   empty hold holds no material, so no later share depends on it; its next arrivals set its shares.
2. **What leaves is recorded.** Each event reports only its own material: replacement@1 the slots
   whose rows it swapped, this operator the holds it emptied (their amounts before the event,
   summed over the class axis, one per release in label_pools order). The label owner records the
   departing material by label, the pre-event amount times its shares just before the event, in
   cumulative records from t = 0, rows and holds apart, so the two events still commute (§9.16,
   item 2). Removal stays apart from degradation, booked to the departing producer's label.

### 9.19 Erratum F: the cohort is marked on the chain's own schedule, and leaves at the gross loss

*23 November 2026, the lead's ruling (D306, item 3) on a split that an independent checker found.
Docs only, tagged before FR-38's rule.*

1. **The definition (§9.8).** FR-38's cohort is the molecules that detach from their template
   during [t1, t2), in the requester's words "detaches from its template" and "the same molecules".
   - It is marked on the chain's own label schedule, a label source's (D296): the window's label from
     t1, the next label from t2.
   - **A molecule re-synthesised from monomers is not a member.** A degradation's reverse one-way
     move puts it in its row at the species' label in force, never at the chain's.
2. **Why the species' own window is not the cohort.**
   - A fate row's degradation is one-sided only in its booked net move, J_D = k n (1 − e^(y_f)).
     Its one-way parts are the gross loss k n and the re-synthesis k n e^(y_f), and FR-42's label
     owner follows each.
   - So a window on the species' own arrivals also labels the molecules re-synthesised in it.
   - Near the degradation's domain edge (e^(y_f) ≈ 0.34, the checker's world), that cohort held 70.10
     copies at 240 s, against 59.42 for the template's releases alone: 18% more.
   - On the chain's schedule the cohort met the template-only reference to 6.7 × 10⁻⁷, relative.
3. **Route 2 (§9.8) uses the gross one-way loss.**
   - A member leaves at the gross per-molecule rate k, whatever re-synthesis returns to its row.
   - So route 2 carries the window's releases with the declared first-order k of their fate's loss
     (cohort.py's known-rate form), not with the booked net loss ∫D_F / n_F = k (1 − e^(y_f)).
   - It stays exact for a constant k in a well-mixed row, up to its grid error.
4. **The two readings agree only where e^(y_f) ≪ 1:** the species window against the chain's
   schedule, and the gross loss against the net.
   - At the sheet's own state, e^(y_f) ≈ 9.4 × 10⁻⁹. There the two cohorts differ by 2.6 × 10⁻⁷
     copies at 240 s (4.4 × 10⁻⁹ relative), and R1's and R2's closed forms stand.
   - FR-38's rule judges the chain's schedule, with route 2 at the gross loss.
5. **Unchanged:**
   - the release marks at release (the requester's answer to (e));
   - route 1's error is the share update's split (erratum C);
   - under release-marking, a hold emptied at a replacement is recorded at the base label (erratum
     E).

### 9.20 Amendment G (proposed): producer identity from the replacement events, options and the recommendation

*Proposed 23 November 2026 by the gene-regulation lane for the lead's choice (D306, item 4), to tag
before code. Docs only.*

**The risk.** A producer label is today a declared name on a chain's label schedule (D296, §9.16
item 7). So a schedule that never switches at its cell's replacement is admitted, and so is one that
switches early. An independent checker found both. In the first, the newcomer's 89.55 copies sat
under the founder's label. The requester defines a producer as (cell, occupant generation,
expression chain), preserved across restart and cell reordering, so the label must follow the
events, not a declaration that may disagree with them.

#### 9.20.1 The options

**(a) The engine derives the producer label (recommended).**
- **The declaration.** A labelled species' entry in the label owner may name a chain source with
  `producer: {windows: [{label, from, to}, ...]}`.
- **The derivation, at the definition and on the host.** The owner derives, for each generation k of
  the chain's cell (replacement@1's occupants, keyed by cell ID: the founder k = 0, then each
  newcomer in event order):
  - the producer label `<cell>-g<k>-<chain>`, and for each declared window
    `<cell>-g<k>-<chain>-<window label>`;
  - the source's schedule: the generation's label from its birth, its window label inside each
    window, and the next generation's from the next event's step.

  These are exactly the per-source schedules a correct hand-written declaration gives, so the
  device's per-source arrival controls (source_controls) are unchanged in form.
- **One authority:** a hand-written schedule for a source declared `producer` is refused.
- **Owners:** the kinds owner (species_labels.py: the key, the derivation, the label list within
  MAX_LABELS, the refusal), and the gene-regulation lane (worlds, replace_restart.py and its test to
  use it). replacement@1 is read only, through species_common.occupants.

**(b) Refuse an inconsistent schedule at the definition.**
- Each producer label carries its triple (cell, generation, chain) in the declaration.
- The definition check refuses any source schedule whose label's generation is not its cell's
  occupant generation at every step: a missed switch, an early or late one, a wrong cell or chain.
- **Owners:** the kinds owner (the check and the triple), and the gene-regulation lane (worlds and
  tests keep writing the schedules).

#### 9.20.2 Trade-offs

| | (a) derived | (b) refused if inconsistent |
| --- | --- | --- |
| Declarations | one key per producer source; no schedule to write | every schedule by hand, plus the triple per label |
| What can go wrong | nothing the events do not fix: the names follow them | caught, but each definition must still be right by hand |
| Without the key or without replacement | no change: host-side only, no new field | no change: a definition check only |
| Programs | the same per-source controls as a correct hand schedule, so bit for bit that run | the same |
| Restart | the labels derive from the definition, so a resume derives the same; the checkpoint carries the shares | the same |
| Cell reordering | names by cell ID and generation by event order, so reordering moves nothing | the same if the check keys by ID |
| Freedom | a producer source's labels are the engine's convention | any schedule that agrees with the events |
| Price | owner about 0.75–1 day; gene lane about 0.25–0.5 | owner about 0.5–0.75 day; gene lane about 0.25 |

**The recommendation is (a).** It removes the error rather than catching it, it writes the
requester's definition into the engine, and it costs about half a day more than (b). The label
names become a contract convention, which a requester reads as the triple.

#### 9.20.3 What it does not change

- The rows a newcomer brings take the species' label in force (§9.16 item 7, erratum E); only the
  chain's products carry the producer label.
- Release-marking and completion-marking (§9.1, erratum C) and the cohort on the chain's own
  schedule (erratum F) are unchanged. A window of (a) is that schedule's window, crossed with each
  generation.
- MAX_LABELS still bounds the labels: generations times (windows + 1), plus the species' own.

### 9.21 Erratum H: route 2 at the node runs at the gross loss (§9.17.5)

*23 November 2026, the lead's ruling, docs only, tagged before amendment T's code. Item 3 is proposed
with it for the lead's choice at the tag.*

1. **Route 2 at node o runs at o's gross one-way loss,** by erratum F's reasoning (§9.19). This
   replaces §9.17.5's "∫D_o over n_o".
   - A producer's molecule at o leaves at o's outside degradation's declared first-order rate k_o,
     whatever re-synthesis returns to o's row.
   - A molecule re-synthesised at o from its monomers takes the species' label in force at o, never
     a producer's. So it is no producer's RNA and no member of a release window's cohort.
   - The booked net loss, ∫D_o/n_o = k_o (1 − e^(y_o)), counts re-synthesis too. The two readings
     agree only where e^(y_o) ≪ 1.
2. **The readouts' route 2** (§9.17.5), each exact for constant rates in a well-mixed row or node,
   up to its grid error (cohort.py's known-rate form):
   - **extracellular RNA by producer:** each producer's exports, its chain's export counter over each
     generation's life, carried at k_o;
   - **the release-marked cohort at o:** two pools in series. In the fate row the window's members
     leave at the fate's gross k_f and by export; their exports then leave o at k_o;
   - **RNA at o from a generation replaced later:** the first readout's route 2 over that
     generation's life.
3. **The export's label report** (§9.17.4), proposed:
   - **(a), recommended:** two one-way transfers per export, as FR-42 reads every two-sided move
     and as this operator already reports a degradation's re-synthesis apart from its loss:
     - the forward part, k_E n_F,c φ_E, from c to o with c's shares;
     - the backward part, k_E n_F,c φ_E e^(x_E), from o to c with o's shares (the same molecules
       returning).

     Their difference is J_E, so the physics is unchanged. A forward and a backward export counter
     (zero-size without an export) let the cohort's series in item 2 carry its members by both
     parts.
   - **(b), as tagged:** one transfer of the net J_E with c's shares. It is exact only where
     e^(x_E) ≪ 1. A driven export far inside its domain meets that, but the domain's own bound,
     x_E ≤ X_DOM = −1, admits e^(x_E) up to e^(−1).

### 9.22 Erratum I: membership classes, and the excess over a blank

*24 November 2026, the user's decision on FR-38's second registered comparison (D334). Docs only,
tagged before that comparison's rule. It names the quantities that the first comparison read under
one name (D313, D316), so that the engine side, the references and the judge read one definition.*

1. **A fate's loss has two one-way parts** (§9.2). For fate row f, with amount n_f and declared
   first-order rate k_f:
   - the **forward (gross) loss** is J⁺_f = k_f n_f, so every molecule present leaves at the
     per-molecule rate k_f;
   - the **re-synthesis** is J⁻_f = k_f n_f e^(y_f), which makes new molecules from monomers;
   - the booked net loss is J_f = J⁺_f − J⁻_f = k_f n_f (1 − e^(y_f)).
2. **Membership.** Each molecule in a fate row belongs to exactly one class, fixed by how and when
   it entered the row. It leaves its class only by a forward move, at the per-molecule rate k_f.

   | Class | Its members | Its law |
   | --- | --- | --- |
   | Pre-existing, P_f | present at t = 0 | dP_f/dt = −k_f P_f |
   | Re-synthesised, B_f | entered by re-synthesis, at any time | dB_f/dt = J⁻_f − k_f B_f |
   | Released in an interval I, C_f(I) | released from the hold during I | dC_f/dt = Q_f 1_I(t) − k_f C_f, with C_f = 0 before I opens |

   - Q_f is §9.2's release into f.
   - An interval is closed on the left and open on the right. A release joins the interval in force
     at the start of its step (§9.12, reading 7; erratum F).
   - For any partition of [0, t] into intervals, the classes sum to the row:
     n_f = P_f + B_f + Σ_I C_f(I).
   - Only the re-synthesised class's inflow reads e^(y_f). Every other class is independent of the
     monomer pool, the volume and re-synthesis.
3. **FR-38's cohort** (§9.8, erratum F) is the class released in the window, C_f(W).
   - Route 1 reads it from FR-42's shares on the chain's own schedule.
   - Route 2 integrates it from the release counter at the declared k_f.
   - Both are the gross reading.
   - **The released molecules still present** are S_f = Σ_I C_f(I) over every interval since
     t = 0, also gross.
4. **The excess over a matched blank, X_f = n_f − n_f^blank, is a pool difference, not a class.**
   - X_f = S_f + (B_f − B_f^blank), since the pre-existing classes are equal in both runs. So X_f
     carries re-synthesis and the coupling through the monomer pool. At an idle fate, S_f is
     exactly zero, while X_f in general is not.
   - X_f is named the excess over the blank (`excess_over_blank`), never "the survivors" or "the
     released molecules still present".
   - This corrects §9.10's "quantity compared" (erratum A, R-F2) and §9.12's reading 4, which named
     the row minus the blank "the released molecules still present". The two agree only where
     e^(y_f) ≪ 1 and the coupling through M is negligible.
5. **The matched blank** of a world whose chain initiates is the same world with H(0) = 0 and the
   chain's k_I = 0, so that nothing completes and nothing is released. Every other declaration is
   equal. Where k_I = 0 already, this is §9.12's reading 3.
6. **The net tracker** dC̃_f/dt = Q_f 1_W − k_f (1 − e^(y_f)) C̃_f follows no set of molecules.
   - It is not FR-38's cohort.
   - It is what a separately rowed class minus its blank gives (the first comparison's references'
     `route1_blank`), and what a tracker at the booked net per-molecule rate gives.
   - It may be published only to size a planted error.
7. **Structural zeros.** An idle route (p = 0 or 1, §9.2) releases nothing, so every class it would
   feed is exactly zero, as are its counter and its heat. A pool difference at an idle fate is not
   one of these zeros.
8. **Unchanged:**
   - release-marking (the request's answer to question (e));
   - the step-start rule;
   - erratum C's split;
   - erratum F's definition of the cohort and route 2's gross loss.
