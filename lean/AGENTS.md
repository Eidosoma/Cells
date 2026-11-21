# Cells Lean charter

For each new physics claim, look first for a theorem we can reuse from the pinned Mathlib, Physlib or a specialist library already used here. A brief search is enough. Prefer public, licensed work with identifiable maintainers or research authors and an inspectable proof. Check that its assumptions, units and sign conventions match the Cells law. Use `#print axioms` on the specialization to see what it relies on. Record additional physical postulates and count a result as proved only when its proof is free of placeholders.

Use the smallest compatible import and write the Cells specialization beside the law. Keep a short proof local when importing would take more work than it saves. A comparison that needs a different toolchain can run as an optional check. Preserve attribution and required license notices when adapting or copying source.

In the claim’s existing `formal.sources`, link the upstream declaration at a fixed revision and say whether Cells imports it, specializes it in an optional check, or proves the formula locally. Keep the compiled engine comparison and the biological measurement in their own fields. [Examples and build commands](README.md#reusing-a-proof)
