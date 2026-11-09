"""Vectorized resolved_pump_tissue@3 worlds are bitwise identical to single-world runs
on CPU when XLA's algebraic rewrites and fusion are disabled in both (a diagnostic
compiler setting, in a subprocess). With default flags the programs differ only in
those rewrites and fused multiply-adds (tests/unit/test_vector_windows_v3.py bounds
the effect). The worlds carry all five channel laws, switched on mid-run.
"""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SCRIPT = textwrap.dedent(
    """
    import json, sys
    import jax, numpy as np
    jax.config.update("jax_enable_x64", True)
    sys.path.insert(0, sys.argv[1])
    from tests.unit.test_vector_windows_v3 import POLICY, cohort, definition
    from cells.core.vector_windows import run_vector_windowed
    from cells.core.windows import run_windowed
    spec = cohort([definition(scale=1 + 0.1 * i) for i in range(3)])
    batch = run_vector_windowed(spec, POLICY)
    equal = []
    for world in spec.worlds:
        own = run_windowed(world.simulation, POLICY).final.state
        mine = batch.worlds[world.world_id].final.state
        equal.append(all(np.array_equal(np.asarray(a), np.asarray(b)) for a, b in zip(mine, own)))
    print(json.dumps(equal))
    """
)


def test_batch_is_bitwise_when_compiler_rewrites_are_disabled_in_both():
    """The vectorized @3 arithmetic, channel populations included, is the scalar one."""
    env = dict(
        os.environ,
        XLA_FLAGS="--xla_disable_hlo_passes=algsimp,fusion",
        JAX_PLATFORMS="cpu",
        JAX_ENABLE_X64="1",
        PYTHONPATH=os.pathsep.join([str(ROOT / "src"), str(ROOT)]),
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", SCRIPT, str(ROOT)],
        env=env,
        capture_output=True,
        text=True,
        timeout=1800,
        check=True,
    )
    assert json.loads(result.stdout.strip().splitlines()[-1]) == [True, True, True]
