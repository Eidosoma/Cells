# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
# ruff: noqa: F821
"""Selected literal phase-cache constructor bodies; no lazy cache evaluation.

The driver supplies private import/helper namespaces and the original vector
constructor's class cell. Decorators, annotations and subsequent phase stores
are outside this selected body boundary.
"""


class PhaseCacheContinuation:
    def attach(self):
        self.cache = SimPhaseCaches(phase=self)


class CacheConstructor:
    def __init__(self, phase):
        from betse.science.math.cache.cacheupscaled import SimPhaseCacheUpscaled
        from betse.science.math.cache.cachevec import SimPhaseCacheVectorCells
        from betse.science.math.cache.cachevecfld import SimPhaseCacheVectorFieldCells

        self.upscaled = SimPhaseCacheUpscaled(phase)
        self.vector = SimPhaseCacheVectorCells(phase)
        self.vector_field = SimPhaseCacheVectorFieldCells(phase)


class CacheABCConstructor:
    def __init__(self, phase):
        self._phase = pyref.proxy_weak(phase)


class CacheVectorConstructor:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        from betse.science.math.cache.cachelyrvec import SimPhaseCacheLayerCellsVector

        self.layer = SimPhaseCacheLayerCellsVector(self._phase)


def proxy_weak(obj):
    return obj if isinstance(obj, WeakRefProxyTypes) else weakref.proxy(obj)
