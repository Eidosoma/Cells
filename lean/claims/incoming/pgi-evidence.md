# Phosphoglucose isomerase concentration and acquisition audit

Eicher et al. (2012) used ³¹P NMR to follow glucose-6-phosphate (G6P) and fructose-6-phosphate (F6P) in extracts of *E. coli* K-12 W3110. The worksheet supports a comparison of the measured soluble hexose-phosphate sum over time. It shows endpoint deviations in both directions, and the exact cause and statistical uncertainty of those deviations remain unresolved. [Primary article, Figures 4–5 and §§2.2, 3.3–3.4](https://www.mdpi.com/2218-1989/2/4/818)

## Worksheet measurements

Open `metabolites-22454-supplementary/supp_data.ods` inside the publisher's ZIP and select the `PGI` sheet. Row 1 labels the upper block “Raw integral data.” Its G6P and F6P entries are already processed concentration estimates in mM. The first time is 1.33 min and subsequent times are spreadsheet formulas that add 1.33 min. Use the concentration columns as stored and view the time column as a nominal grid. Row 40 starts the spline block and row 43 is its first numeric row. [Publisher download](https://mdpi-res.com/metabolites/metabolites-02-00818/article_deploy/metabolites-02-00818-s001.zip)

The table sums only the first and last rows of each measured concentration series. The within-course range is the minimum and maximum sum over all the measured rows. These ranges describe variation across time and cannot give replicate measurement uncertainty.

| Dataset | Time, G6P and F6P cells | Points | Time window (min) | Initial sum (mM) | Final sum (mM) | Change (mM) | Range (mM) |
| --- | --- | ---: | --- | ---: | ---: | ---: | --- |
| 1 | `A4:C30` | 27 | 1.33–35.91 | 8.395747 | 7.782390 | −0.613357 | 7.582–8.995 |
| 2 | `F4:H33` | 30 | 1.33–39.90 | 6.887225 | 5.352327 | −1.534898 | 5.038–7.295 |
| 3 | `K4:M29` | 26 | 1.33–34.58 | 9.584450 | 9.683752 | +0.099302 | 8.650–10.090 |
| 4 | `P4:R15` | 12 | 1.33–15.96 | 3.695430 | 4.086513 | +0.391083 | 3.695–4.804 |
| 5 | `U4:W34` | 31 | 1.33–41.23 | 7.268005 | 7.060496 | −0.207509 | 5.718–7.841 |

For example, `(B30 + C30) − (B4 + C4) = −0.61335674989819 mM` from the stored decimals. `B43 + C43` and `B69 + C69` are the corresponding first and last spline values at those nominal times and should be omitted from the measurement summary. Figure 4A reports a 60° pulse, 0.8 s acquisition, 0.5 s relaxation and a 47-minute acquisition, with nominal 8.5 mM F6P and no G6P initially and rounded final concentrations of 5.0 and 2.8 mM. Keep those figure values distinct from the 27 measured points assigned to dataset 1. The 8.5 mM figure preparation is also distinct from dataset 1's first *measured* sum at 1.33 min. [Article, Figures 4A–5](https://www.mdpi.com/2218-1989/2/4/818)

## Mapping the five courses to acquisition records

The order in `metabolites-22454-supplementary/pgi_fids.zip` → `list.txt` corresponds to the order used for kinetic fits. The direction of the measured substrate and product changes is consistent with that order. The two similarly named F6P directories in the second entry are consecutive acquisitions within one course. The names indicate nominal sample labels and cannot establish concentrations measured in the tube. [Publisher supplement](https://mdpi-res.com/metabolites/metabolites-02-00818/article_deploy/metabolites-02-00818-s001.zip)

| Dataset | `list.txt` assignment, in order | Contents in the archived directory |
| --- | --- | --- |
| 1 | `06_06_2011_PGI_10mMf6p_10mMatp.fid/` | `fid`, `log`, `procpar`, `text` |
| 2 | `19072012_0g6p_10f6p.fid/`, `19072012_0g6p_10f6p_2.fid/` | Two empty directory entries |
| 3 | `19072012_10g6p_0f6p.fid/` | Empty directory entry |
| 4 | `19072012_5g6p_0f6p.fid/` | Empty directory entry |
| 5 | `19072012_5g6p_5f6p.fid/` | Empty directory entry |
| Relaxation calibration | `19072012_calib30s.fid/` | Empty directory entry |

**Published protocol.** Figure 5 and §3.3 describe 25 °C, a Varian 600 MHz instrument with ³¹P at 242.87 MHz, a 90° pulse and 80 transients per FID at 1.0 s acquisition and no added relaxation delay. The standard preparation fills a 5-mm NMR tube to 1.00 mL with pH 7.2 PIPES and includes cell extract, an internal triethyl phosphate (TEP) standard, D₂O and Mg²⁺. The reaction starts before the tube is reinserted and acquisition waits for a lock. The nominal first workbook time cannot establish exactly how far the reaction advanced before the first recorded spectrum. [Article, Figure 5 and §3.3](https://www.mdpi.com/2218-1989/2/4/818)

**First listed acquisition.** `procpar` records `temp = 25`, `tn = P31`, `sfrq = 242.8754193`, `at = 0.4960256`, `d1 = 0.5`, and `arraydim = 30` with 100 transients per element. The `text` file gives a final volume of 950 μL, 20 μL of extract, 0.5 mM TEP and 1.40 min per FID. These metadata differ from the article’s standard 1.00 mL assay, its Figure 5 80-transient protocol and the workbook cadence of 1.33 min. The mapping is supported by list order. The exact relationship between the 30-element FID, the 27 imported worksheet rows and their timestamps is unresolved, so a new re-integration or timing reconstruction is premature. Taking the 950 μL volume provisionally for dataset 1 would give about −0.583 μmol (−5.83 × 10⁸ fmol) of measured soluble pool change. Per-course volumes for datasets 2–5 are unverified. [Publisher supplement, first listed `procpar` and `text`](https://mdpi-res.com/metabolites/metabolites-02-00818/article_deploy/metabolites-02-00818-s001.zip)

## Calibration and scope of the balance

- TEP supplies a shared concentration reference. The standard assay lists 50 mM TEP, while the first FID directory's `text` lists 0.5 mM. Use the archived worksheet concentrations for the descriptive analysis. The data do not resolve which TEP calibration coefficient was applied to each course.
- With a common reference integral `I_TEP`, both concentration estimates share its error. A fixed multiplicative calibration error rescales both endpoints and their difference. A time-varying reference error can produce drift in their sum. Treating the two metabolite estimates as independent overstates the information available for propagating uncertainty. The variance of their sum includes `2 Cov(G6P, F6P)`. An endpoint change also depends on covariance across times.
- The paper used a 30 s calibration spectrum to correct incomplete relaxation. It reports TEP `T₁` near 6 s and metabolite values down to 0.2 s. The listed calibration folder is empty, and the workbook has no separate time series of TEP peak areas or per-point relaxation corrections. Peak overlap, integration and differential relaxation can add species-specific errors. The reported day/extract normalization is for rates and supplies no concentration error bars. [Article, §§3.3–3.4](https://www.mdpi.com/2218-1989/2/4/818)
- The study reports no observed exit reactions in these PGI assays. The worksheet sums the assigned soluble G6P and F6P signals. It does not independently quantify enzyme-bound species, unresolved resonances, assay losses or possible low-abundance products in the extract. These are candidate gaps in the inventory, with their magnitudes and effects unknown. The conservation claim is therefore not adjudicated by the endpoint drift.

## Source identity

Eicher, Snoep and Rohwer’s 2012 article lists the original workbook and both NMR archives. The publisher identifies the article licence as CC BY 3.0. Use the publisher download above and the checksums below to identify the files used here. [Article and supplement listing](https://www.mdpi.com/2218-1989/2/4/818) · [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/)

| Object | SHA-256 |
| --- | --- |
| `eicher-2012-supplement.zip` | `b8b01bb3f6ea2e3aae8c3958f42474d8afaf13fccd7792088f30e1e8dd2c77f9` |
| `supp_data.ods` | `a799d88c5b596d69f19355ab5a92f6ae373d306af7ad9d921d30dd2b30efd2a7` |
| `pgi_fids.zip` | `782dc512d4018492a8b9edb273436536c535843c39f57384952abf83736286e8` |
