# J1 declared inputs: rationale (S0b step 1)

Declared on 11 November 2026, before any model computed an Em for J1. The machine-readable
file is [`j1_declared_inputs.json`](j1_declared_inputs.json); the reference (R-full) reads it
directly. Design: [CELL_DIVISION_DESIGN.md](../../docs/CELL_DIVISION_DESIGN.md) §7, §8.1, §9.

**J1.** dLB74 Table I, normal eggs at onset of second cleavage (30 min): Em −20.3 ± 0.8 mV
(SE, n = 20) is predicted; Rm 488 ± 28 kΩ (n = 17) from the same series calibrates the cleft
access factor A/L. The prediction of record is R-full's Em under every default.

## What is declared, and why

- **Rm is a simulated pulse response** (dLB74 p530): ±30 nA, 1.2 s, every 10 s, alternating,
  running throughout. Em is the sample at a pulse's front edge; each deflection is the sample
  1 s later, inside the pulse; Rm is the mean of one depolarizing and one hyperpolarizing
  chord. The same rule sets the old membrane from Rm 852 kΩ at onset of first cleavage,
  replacing the smoke test's slope at rest.
- **New membrane.** r_new 1.59 kΩ·cm² (arms 1.36 and 1.82) becomes a permeability through the
  constant-field slope at −60 mV against the bath, the condition of its measurement (the
  exposed arms sat at −60 mV). P_Na/P_K comes from inverting the two exposed arms' branch
  EMFs (−90.8 and −74.4 mV): 0.019 to 0.048, default their mean 0.034. P_Cl = 0. All new
  membrane faces the lumen.
- **Insertion.** The total at J1 (1.39 mm², BdL73) and the onset (7 min, range 6–8) are
  primary; the uniform rate follows (0.060 mm²/min). A constant 0.04 mm²/min would miss the
  total, so the low end of the 0.04–0.06 range enters as a back-loaded schedule.
- **Lumen.** Volume w × one face (A_new counts both faces); w 2.0 µm, range 1.5–2.5. It
  fills with bath fluid as it grows.
- **Access.** One face with a single A/L and free-solution diffusivity ratios. Only the ratios
  matter after calibration, so the temperature factor cancels.
- **Ranges and the band.** Stated ranges are used as given; measured means that have none
  enter at ±1 SE (the Rm targets, area, cytosol). Each input moves one at a time, with every
  calibration redone; the band is the worst-case sum of the shifts, checked on the corners of
  the three largest. Arms are reported, not banded.
- **Maximum band width: 8 mV**, tolerances included. The firmer failure limit is the sealed or
  identical-membrane value, the old membrane's zero-current potential (−9.9 mV; measured
  −9.7). A band that passes against the datum's ±2 SE can reach −18.7 mV + W, so it excludes
  that limit for every passing position only if W < 8.8 mV. The bath-equivalent limit
  (−37 to −44 mV) allows 15 mV and does not bind.

## For the lead to settle at registration

1. **Access law.** The brief says constant field; the engine's faces are
   `logmean_electrodiffusion@1`. Recommended default: log-mean. The rim access is aqueous and
   electroneutral, where the log-mean law is exact for linear concentration profiles and
   constant field (a linear potential) is a membrane assumption; and R-full and the S4 engine
   run then share one law. The other is a reported arm either way.
2. The cation-selective seal and w = 0.5 µm as reported-only arms.
3. The back-loaded schedule inside the band.
4. The 8-mV maximum.
