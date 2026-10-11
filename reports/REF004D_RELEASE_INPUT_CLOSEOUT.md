# REF-004d: native input / single-update closeout

2026-09-15, D103. The separately registered saved-data review **passes** in
24.469267 s, finishing at 22:18:23 UTC. This closes input application and two
single updates per fresh phase, not the proposed 2 ms release experiment.

The review reconstructs **916,176 comparisons**, with **zero failures**, across
144 fresh phases, 288 single updates, 288 input applications and 72 observer
pairs. All 1,776 zero-flux bath means match the pinned source-order reduction
exactly. The 104 nonidentical means and all 104 original exact-identity
rejections are preserved. Maximum rounding is one ULP: 8.881784197001252e-16 mM,
or 5.995204332975845e-15 fmol. The worst scaled physical error is
0.010904300881093102 against a pass limit of 1. No physical budget was changed.

The ten-file review packet, 175 review sources, 15 prior reports and all
605 original capture files / 165 original inputs authenticate unchanged.
The review imports no simulator or numerical library and performs no numerical
integration. D102's original failed receipt and its checker remain immutable.

- Review: `runs/ref-004d-release-review-2026-09-15/review-01`.
- Completion SHA-256:
  `a3660e211dbd5cd2e2e6389d8a0ff46d15019842dd620a4114016157af5152ad`.
- Registration SHA-256:
  `bbb923316e0bc057fc083dffceebf5fdecd97e811cbe30ac06b796beb91dc864`.
- Software: 66 tests pass in 10.66 s; XML SHA-256:
  `7b593a5ba0c6189e27633e99cd75ecb9d5beee3f28425280350b8777a250b5a4`.

The native queries at 0, 0.5 and 1 ms select inputs; they are not intervening
elapsed integration. Full-loop timed dispatch, release trajectories, native
restart, biological validity and GPU execution are still unqualified. Production
remains stable 0.14.0 / accepted development 0.15.0.dev0. The next gate is an
independent piecewise reference, followed later by actual simulator comparison.
