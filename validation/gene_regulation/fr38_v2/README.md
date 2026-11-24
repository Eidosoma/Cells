# FR-38's second registered comparison: the builder's and the judge's tools

The registration is `docs/FR38_SECOND_COMPARISON_PROTOCOL.md` with the spec folder `spec/` (tag
`fr38-v2-spec-amendments-2026-11-24`: the criteria tag `fr38-v2-criteria-2026-11-24` with
amendments 1 and 2). The code-blind references are tagged `fr38-v2-references-2026-11-24` (D339).
Decisions: D334 (arms A and B decide FR-38's verdict; C and D carry their own) and D339.

| File | What it does |
| --- | --- |
| `reader.py` | The judge's reader (CRITERIA.md C0): each reference file read by structure, its classes, units, inputs and accuracies checked, and one normalised structure returned for the judge. `--check-reader` is its first read of `reference_invented.json`, beside made-up documents in every family's layout and planted faults |

The lead gives this one brief both the builder's and the judge's parts, which the protocol's §5
separates into two roles. The judge's tables in `reader.py` are its own transcription of the spec,
kept apart from the builder's worlds, so that C0's check of an engine run's definition compares two
transcriptions.

## The inputs' echo (C0)

The reader checks each reference file's `inputs` by name, under the lead's rule of 24 November 2026:
- every known key is held to SPEC.md's (or A1's sheet's) stated value, to 1e-12 relative;
- a key whose value the spec states but the file lacks is a refusal;
- a key in the file with no stated value is listed as unchecked, never refused.

The names are the references agent's. The lead read them from the five files (names only, no value)
before the reader's tag. The values below are SPEC.md's inputs, not reference results.

### AF, AN, C and D: the invented file's 37 names (SPEC.md §1.1, §1.2)

| Key | SPEC.md's quantity | Stated value |
| --- | --- | --- |
| `H0_copies` | The hold's start H(0) | 160 copies |
| `K_N_mM` | N's saturation constant | 0.02 mM |
| `L_residues` | L | 1200 |
| `N_per_residue` | N drawn per residue | 1 |
| `Pi_per_residue` | Pi released per residue | 2 |
| `bath_mM` | The bath's K and Y | 140 mM each. In D, 56 mM (0.4 of 140) or §1.1's 140 beside `water.bath_fraction_of_section_1_1` |
| `bath_trace_mM` | The bath's traces | 1e-15 mM. In D, 0.4e-15 mM or §1.1's 1e-15, likewise |
| `bath_volume_pL` | The held bath's volume | 1.0 pL |
| `blank` | The matched blank | H(0) 0 copies, k_I 0 |
| `cell_background_mM` | The cell's K and Y | 140 mM each |
| `constants` | N_A, k_B, R = fl(N_A k_B), T, RT = fl(R T), c° and the copy | SPEC.md §0; amendment 1, reading 5 |
| `horizon_s` | The horizon | 14,400 s |
| `initial_copies` | R(0) and R_s(0) | 20 and 15 copies |
| `initial_label_shares` | The initial shares in the cell | `pool0` 1.0 |
| `initial_mM` | N, M and Pi at t = 0 | N 2.0, Pi 5.0; M 0.05 (AF) or 4.0e-3 (AN, C, D) mM |
| `k_I_per_mM_s` | Initiation k_I | 3.0e3 mM⁻¹ s⁻¹ |
| `k_d_per_s` | `deg_R`'s k_d | 1/9000 s⁻¹ |
| `k_s_per_s` | `deg_R_s`'s k_s | 1/1350 s⁻¹ |
| `label_schedule_s` | Transcription's source schedule | `pre` 0, `win` 1800, `post` 5400 s |
| `moieties` | Phosphorus and nucleoside over N, M, Pi, R and R_s | SPEC.md §1.1 |
| `mu0_RT_at_1M` | μ°/RT at 1 M of N, M, Pi, R and R_s | N 24.8672029410015, M and Pi 0; R and R_s 10319.123756415122 (AF) or −12442.6668 (AN, C, D) |
| `mu_res_RT` | μ°_res as the engine forms it, fl(μ°_R/1200) | 8.599269797012601 (AF), −10.368889000000001 (AN, C, D); amendment 1, reading 6 |
| `mu_res_declared_RT` | μ°_res as SPEC.md declares it | 8.599269797012601 (AF), −10.368889 (AN, C, D) |
| `output_interval_s` | The output grid's step | 30 s |
| `p_sched` | The scheduled p | 0.7 from 0, 0.25 from 2700 s |
| `patch_area_m2` | The patch's area | 1e-10 m² |
| `patch_solute_permeability` | Every solute permeability | 0 |
| `pool_machines_copies` | Pool `pol` | 10⁴ copies |
| `runs` | Each run's machine and p; the blank's H(0) and k_I | SPEC.md §1.2, §1.3 |
| `samples_s` | The cohort's sample times | 5400, 9000 and 12,600 s |
| `speed_nt_per_s` | v | 50 nt/s |
| `stages` | The stages | 8 |
| `tau_s` | The release's mean dwell τ | 2400 s |
| `template_copies` | The gene's copies | 1 |
| `trace_mM` | The rows' trace outside the cell | 1e-15 mM |
| `volume_pL` | The cell's (reference) volume | 1.0 pL |
| `window_s` | W = [t1, t2) | [1800, 5400) s |

### C: `store` (SPEC.md §1.5)

| Key | SPEC.md's quantity | Stated value |
| --- | --- | --- |
| `store.Mx_initial_mM` | Mx in the cell at t = 0 | 1.0e-6 mM |
| `store.Mx_moieties` | Mx's moieties | nucleoside 1, phosphorus 1 |
| `store.forward_per_s_at_c0` | `store_M`'s forward rate at c0 | 1/3000 s⁻¹ |
| `store.mu0_Mx_RT_at_1M` | Mx's μ°/RT at 1 M | 0.0 |
| `store.multiplier` | The reaction's multiplier from t = 0 | 1 (as a number or a one-entry schedule) |
| `store.network_c0_mM` | The network's c0 | 1 mM |
| `store.network_mu0_RT_at_c0` | M's and Mx's μ°/RT at the network's c0 | −6.907755278982137 each |

### D: `water` (SPEC.md §1.6)

| Key | SPEC.md's quantity | Stated value |
| --- | --- | --- |
| `water.L_p_m_per_Pa_s` | The patch's hydraulic permeability | 2.8029294930351318e-14 m Pa⁻¹ s⁻¹ |
| `water.V_max_pL` | The maximum volume | 3.0 pL |
| `water.V_min_pL` | The minimum volume | 0.5 pL |
| `water.V_ref_pL` | The reference volume | 1.0 pL |
| `water.availability` | The patch's water availability from t = 0 | 1 (as a number or a one-entry schedule) |
| `water.bath_fraction_of_section_1_1` | The bath's amounts as a fraction of §1.1's | 0.4 |
| `water.bath_pressure_Pa` | The held bath's hydrostatic pressure | 0 Pa |
| `water.bulk_modulus_Pa` | The bulk modulus | 0 Pa |
| `water.impermeant_fmol` | The impermeant amount | 0 fmol |
| `water.pressure_offset_Pa` | The pressure offset | 0 Pa |

### B: 46 names (SPEC.md §2, with the sheet's §5.1 table)

The 19 it shares with the invented file:

| Key | SPEC.md's quantity | Stated value |
| --- | --- | --- |
| `H0_copies` | H(0) | 0 |
| `constants` | As above | SPEC.md §0 |
| `horizon_s` | The horizon | 21,600 s |
| `initial_label_shares` | The initial shares (the trace) | `pool0` 1.0 |
| `initial_mM` | A1's initial state, with R_s at R's trace | X 1.0e-3, N 2.0, M 0.05, A 2.0, ATP 5.0, ADP 0.5, Pi 5.0, R, R_s and P 1.0e-12 mM |
| `k_I_per_mM_s` | Transcription's initiation | 1.2e4 mM⁻¹ s⁻¹ (A1's k_I_tx) |
| `k_d_per_s` | `deg_R`'s k_d | 1/8000 s⁻¹ |
| `k_s_per_s` | `deg_R_s`'s k_s | 1/1100 s⁻¹ |
| `label_schedule_s` | Transcription's source schedule | `pre` 0, `win` 2400, `post` 6000 s |
| `moieties` | The sheet's §1.4 moieties over B's rows | Checked where the moiety's name is the sheet's (`amino acid` written either way); never required by row |
| `mu0_RT_at_1M` | μ°/RT at 1 M | ATP 12.409206388416035; ADP, Pi, M and A 0; N 24.8672029410015; R and R_s 10319.123756415122; P 2336.405378810971 |
| `output_interval_s` | The output grid's step | 60 s |
| `p_sched` | No schedule: p is constant | [[0, 0.55]] or null |
| `runs` | Each run's machine and p | `p=0.55 returned`, `p=0.55 held`; p 0.55 (a number or a one-entry schedule) |
| `samples_s` | The sample times | 6000, 9600 and 13,200 s |
| `tau_s` | τ | 1500 s |
| `template_copies` | T_copies | 1 |
| `volume_pL` | V | 1.0 pL |
| `window_s` | W | [2400, 6000) s |

B's own 27, each the sheet's §5.1 symbol or SPEC.md §2's value:

| Key | Quantity | Stated value |
| --- | --- | --- |
| `K_ATP_rc_mM`, `K_ATP_tl_mM`, `K_A_tl_mM`, `K_M_rc_mM`, `K_N_tx_mM`, `K_X_mM` | K_ATP_rc, K_ATP_tl, K_A_tl, K_M_rc, K_N_tx, K_X | 0.1, 0.02, 0.02, 0.1, 0.02, 1.0e-3 mM |
| `L_P_aa`, `L_R_nt` | L_P, L_R | 400, 1200 |
| `M_pol_copies`, `M_rib_copies` | M_pol, M_rib | 1e4, 1e6 copies |
| `P_on_fmol_per_s` | P_on | 2.0e-6 fmol/s |
| `V_C_mM_per_s` | V_C | 0.01 mM/s |
| `b_X`, `n_X` | b_X, n_X | 0.02, 2 |
| `k_I_tl_per_mM_s`, `k_I_tx_per_mM_s` | k_I_tl, k_I_tx | 120, 1.2e4 mM⁻¹ s⁻¹ |
| `k_P_per_s`, `k_X_per_s` | k_P, k_X | 5.0e-4, 2.0e-3 s⁻¹ |
| `m_tl`, `m_tx` | m_tl, m_tx | 8, 8 |
| `mu_res_P_RT`, `mu_res_R_RT` | fl(μ°_P/400), fl(μ°_R/1200) (amendment 1, reading 6) | 5.841013447027427, 8.599269797012601 |
| `p` | p | 0.55 |
| `t_end_s`, `t_off_s` | t_end, t_off | 21,600, 10,800 s |
| `v_tl_aa_per_s`, `v_tx_nt_per_s` | v_tl, v_tx | 16 aa/s, 50 nt/s |

B lacks 18 of the invented file's names (the hold world's own: `K_N_mM`, `L_residues`,
`N_per_residue`, `Pi_per_residue`, `bath_mM`, `bath_trace_mM`, `bath_volume_pL`, `blank`,
`cell_background_mM`, `initial_copies`, `mu_res_RT`, `mu_res_declared_RT`, `patch_area_m2`,
`patch_solute_permeability`, `pool_machines_copies`, `speed_nt_per_s`, `stages` and `trace_mM`), so
the reader does not ask for them there.

## Running

With `/mnt/workspaces/Cells/venv-cpu/bin/python`, `PYTHONPATH=src:.` and `JAX_ENABLE_X64=1`:
- `python -m validation.gene_regulation.fr38_v2.reader --check-reader` reads the invented file from
  the references' tag through git and checks its sha256 against the tag's `SHA256SUMS`;
- `python -m validation.gene_regulation.fr38_v2.reader c0 DIR` is C0 on the five real files, after
  the reader's tag only.
