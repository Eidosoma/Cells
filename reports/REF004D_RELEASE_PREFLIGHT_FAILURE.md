# REF-004d / D102: complete native capture, retained checker rejection

2026-09-15. Read-only investigation following the user-requested status check.
Original directory:
`runs/ref-004d-release-preflight-2026-09-15/capture-01`.

The native worker completed **six preparations, 144 fresh phases, 288 single
updates and 72 observer pairs** in **36.066 s**, with no warnings. The controller
stopped after **52.782 s** in `independent_boundary_comparison`; there is no
completion receipt or accepted D102 result. Status remains
`release_input_preflight_failed_not_qualified`.

## Observed mismatch and source cause

First exact-identity rejection: history a, 25 microsecond step, baseline,
query 0, probe update, `after_ordinary`. All 30 represented K bath entries changed
from **4.000002534737709** to **4.000002534737708 mM**: one ULP, or
**8.881784197001252e-16 mM**. Observer-on/off partners agree exactly. Cell and
membrane concentrations did not change at that boundary.

Pinned BETSE `sim.py:2086` calls `update_Co` for ordinary concentrations even
with zero flux. The non-ECM branch at `sim_toolbox.py:1205` takes the mean of
the 30-face bath vector. The pinned NumPy reduction's operation order can
change the last represented bit of an otherwise uniform vector. Blocked channel
updates also call this same concentration updater.

A read-only equality census found 24 priming ordinary boundaries, 72 probe
ordinary boundaries and eight blocked channel boundaries with nonidentical
bath values. All were K-only, uniform before and after, and at most one ULP.
This census is diagnostic, **not** completed numerical review. It does not
reclassify the original failure or establish that all other full-panel checks
pass. D103 must independently verify the exact source arithmetic and all original
physical budgets across the complete saved panel.

## Frozen evidence

All **605 files / 21,344,575 bytes** remain. D102's 165-input source capsule,
71-test software receipt, eleven prior reports and earlier evidence authenticate.
No captured state, native implementation, production code, original contract or
checker has been changed; no simulator has been rerun.

| Anchor | SHA-256 |
| --- | --- |
| `registration.json` | `5d4f24d7c933ae637957905110ef792684c05d30f31d667da327ebc39a6bd52a` |
| `failure.json` | `a42ff28ee28780f03aa07e40e5efa9225f9657cc8096708b29d5a3639d52b532` |
| `betse.json` | `ce3e650ec43e140458c4dae8bc68f5a6b0a47b99382bfb0267c5e514789aa94e` |
| `launch.json` | `67de69b25120068d354473ada9b1b3420f0f71fb6085bc777bd56fc45684137a` |

The [D103 review contract](../docs/BETSE_CHANNEL_RELEASE_REVIEW.md) amends the
two outside-value identity assumptions to exact source-order remixing checks,
with unchanged physical tolerances and explicit rounding residuals. It is a new
saved-data evidence layer, not a successful rerun of the failed D102 checker.
