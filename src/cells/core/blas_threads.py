"""One BLAS thread for every run, so a CPU run's bits do not follow its allocation (D190).

docs/ARCHITECTURE.md, "Allocation-independent linear algebra": a CPU run's bits follow its CPU
allocation through one channel, OpenBLAS's thread count, which defaults to the CPUs of the
process's affinity and cannot exceed them. Two builds are in play: numpy's, for host work (the
binding-time Cholesky of surface_field.bind, host solves, the analysis tools), and scipy's, which
jaxlib's CPU LAPACK kernels call from inside compiled programs (@3's IMEX step factors its
node-space operator every step). On the 825-node world the binding has one bit class at 1 thread
and another shared by 2 to 16 threads; with both builds at 1 thread, a run on 4 CPUs is bitwise the
1-CPU run, so XLA's own threading moves no bits there.

At `import cells` (pin_at_import), a BLAS that loads later starts at THREADS: OpenBLAS reads
OPENBLAS_NUM_THREADS when it loads, and both builds honour it. One already loaded, when numpy came
first, is set at once by pin(). So a light module such as cells.continuity, imported fresh, still
loads neither numpy nor scipy. pin() loads scipy's LAPACK first (jaxlib loads it only at its first
LAPACK call, and a limit reaches only the libraries already loaded), then sets every loaded BLAS to
THREADS through threadpoolctl. Each run entry point pins again (require_pinned), then reads the
count back and refuses the run if any loaded BLAS is not at THREADS, or if none is found.

libraries() is the run manifest's record of them: each library's API, prefix, version, kernel
architecture and thread count. The bits stay machine-dependent: OpenBLAS picks its kernels by CPU
type, so a bitwise comparison also needs the same libraries on the same kind of CPU.
"""

import os
import sys

THREADS = 1
RECORD_KEYS = ("internal_api", "prefix", "version", "architecture", "num_threads")


def pin_at_import():
    """At `import cells`: a BLAS loaded from now on starts at THREADS, and one already loaded is
    set now; numpy, scipy and threadpoolctl are imported only if numpy already is."""
    os.environ["OPENBLAS_NUM_THREADS"] = str(THREADS)
    if "numpy" in sys.modules:
        pin()


def pin():
    """Every loaded BLAS at THREADS, scipy's LAPACK (jaxlib's) loaded first."""
    import scipy.linalg.cython_lapack  # noqa: F401  (loads scipy's OpenBLAS, which jaxlib calls)
    import threadpoolctl

    threadpoolctl.threadpool_limits(limits=THREADS, user_api="blas")


def libraries():
    """The loaded BLAS libraries, each as {internal_api, prefix, version, architecture,
    num_threads}: the run manifest's record."""
    import threadpoolctl

    return [
        {key: info.get(key) for key in RECORD_KEYS}
        for info in threadpoolctl.threadpool_info()
        if info.get("user_api") == "blas"
    ]


def record():
    """The run manifest's block: threadpoolctl's version and each loaded BLAS library."""
    import threadpoolctl

    return {"threadpoolctl": threadpoolctl.__version__, "libraries": libraries()}


def require_pinned(where):
    """At a run entry point: pin again, then refuse the run unless every loaded BLAS reads back at
    THREADS (D190). Returns the libraries' record."""
    from cells.core.specs import ConfigError  # Here: `import cells` pins before core loads.

    pin()
    found = libraries()
    wrong = [lib for lib in found if lib["num_threads"] != THREADS]
    if not found or wrong:
        raise ConfigError(
            f"{where} runs with every BLAS at {THREADS} thread, so that its bits do not follow "
            f"the CPU allocation (D190); "
            + (f"read back: {wrong}" if found else "no BLAS library was found to pin")
        )
    return found
