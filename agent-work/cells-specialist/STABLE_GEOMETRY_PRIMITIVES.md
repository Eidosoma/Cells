# Versioned stable primitive arithmetic

`cells_stable_binary64_geometry_primitives@1` is a separate host arithmetic law
for polygon centroid/signed area and triangle centre/radii/area. Literal BETSE
primitives, the original failed 19/22 campaign and the frozen lifecycle package
remain unchanged. This package offers no native-equivalence, whole-mesh,
topology, physical-geometry or acceleration qualification.

The saved diagnosis shows why fsum alone cannot fix the centroid: the products
already lost the required bits. It also shows that determinant area avoids the
selected thin-triangle Heron failure. Production therefore uses local moments
and determinant area, with outward intervals around all intermediate arithmetic.
A floating result is accepted only with a complete enclosure within 32 ULPs.
Zero cancellation, uncertain signs, range problems or wide enclosures cause
exact binary-input rational evaluation. Radius and inradius fallback use bounded
integer-root dyadic intervals until binary64 rounding is resolved. Every method
and certificate is retained. No test-specific absolute floor selects a method.

The domain is explicit: finite binary64 points in a simple polygon's supplied
order, or a distinct noncollinear triangle, with at most 64 vertices. Concavity
and forward collinear polygon edges are admitted. Self-crossing/touching,
backtracking, degeneracy, wrong scalar/axis types and nonrepresentable outputs
have distinct refusals. Runtime floating-environment probes precede arithmetic.
Requests and results own immutable data and are sealed against altered method,
certificate, value and ownership claims.

Independent targets use a common integer grid, global shoelace moments and
global centre determinants, plus a separate Decimal Gaussian/Heron calculation.
They preserve thousands of digits at two independently evaluated precisions.
Comparisons use the complete target strings, exact ratios, binary64 bits and
enclosures. Original failing inputs and native outputs remain frozen regression
data. Scale/order/translation controls retain their complete binary64 inputs.
If translating coordinates rounds them, the test records that quantization and
compares the changed primitive rather than claiming exact translation invariance.

The prepared panel has 54 numerical cases, 21 refusals and nine ownership checks.
Fresh reference workers deny production and scientific-package imports. Runtime
inventories include mapped libraries as well as Python modules. Test, reference
and finalization workers use the established bounded resource guard; the outer
supervisor also covers setup and finalization. Metadata and file hashes stream,
and all original failure/diagnostic artifacts remain available.

This round permits source/AST/hash/lint preparation only. No primitive, fixture,
test collection or numerical qualification is executed. Chief coordinates review
and any later detached qualification; the numerical gate stays false.
