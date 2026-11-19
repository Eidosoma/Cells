# **Paper review: Reasoning about the Genetic Code in Lean**

Colin T. Jones & Tyler R. Josephson · October 26, 2026 · arXiv preprint

**Overall assessment:** An interesting proof of concept for applying mathematical verification to biology. Its most important contribution is not discovering something new about genetics, but showing how biological rules can be expressed in software so that a computer can mathematically check whether certain properties always hold.

**My verdict:** Promising methodology, relatively modest scientific contribution, and potentially very relevant to the architecture of Eidosoma's Cells simulator.

The key distinction is:

> A mathematical proof can establish that a simulation follows its specified rules perfectly. It cannot, by itself, establish that those rules accurately describe biology.

The authors understand this distinction and discuss it explicitly. Indeed, it is one of the strongest aspects of the paper.

**Sources:** [Full paper](https://arxiv.org/html/2610.36343?utm_source=chatgpt.com) · [Authors' Lean implementation](https://github.com/ATOMSLab/LeanGenetics?utm_source=chatgpt.com)

## **1. What they did, in simple terms**

Imagine writing a small computer program that mimics how genetic information gets translated into proteins.

DNA

# **TTT**

Genetic sequence

RNA

# **UUU**

Transcription

Protein

# **Phe**

Translation

Example using the DNA coding strand. Phe is phenylalanine, an amino acid.

Instead of merely testing their program with thousands of sequences, the researchers used Lean 4 to prove certain properties for every valid input covered by their definitions.

They formally represented DNA bases, RNA bases, amino acids and the rules connecting them, then checked properties such as:

- **Genetic redundancy:** Different DNA sequences can encode the same amino acid.
- **Transcription consistency:** Their simple DNA-to-RNA operation preserves sequence length.
- **Reversibility:** Under their simplified definitions, RNA transcription retains enough information to reconstruct its original DNA template.
- **Mutation rules:** Replacing one nucleotide does not change sequence length.
- **Replication:** Their DNA-copying model has mathematically predictable properties.

These are established biological or mathematical facts, not new discoveries. The contribution is that the computer can verify the stated properties of the implemented model.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://arxiv.org\&sz=32)

arXiv+1



## **2. The strongest scientific contribution**

The most valuable part of the study is actually the discovery of errors while constructing proofs.

The researchers initially implemented transcription incorrectly. When they tried proving that the coding and template strands produce equivalent RNA, their proof failed.

They had to correct their implementation and explicitly account for the complementary relationship between the two DNA strands.

This illustrates a powerful development methodology:

**Define a biological rule**

For example, complementary DNA strands must produce matching RNA transcripts

**Express an expected property as a theorem**

**Ask Lean to prove the property**

**Proof succeeds**

Property holds under the definitions

**Proof fails**

Investigate model, assumptions or proof

A failed proof does not necessarily mean that the implementation is wrong. The property might be false, the assumptions incomplete, or the proof strategy insufficient. But it forces a precise examination of the underlying model.

That is a meaningful improvement over relying entirely on tests.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://arxiv.org\&sz=32)

arXiv+1



## **3. Problems I found in the paper and implementation**

I inspected the published Lean source code as well as the paper. There are several issues worth distinguishing.

| Issue                               | My assessment                                                     |
| ----------------------------------- | ----------------------------------------------------------------- |
| Incorrect coding-strand example     | Clear explanatory error                                           |
| Malformed codons become STOP        | Important implementation flaw                                     |
| No realistic initiation/termination | Acknowledged biological limitation                                |
| Mutation input validation           | Incomplete constraints                                            |
| Real-world model validation         | Not demonstrated                                                  |
| Reproducibility                     | Source published, but I did not independently run the Lean proofs |

### **A. An actual error in the paper**

In section 3.3, the authors state that coding-strand DNA sequences `AAA` and `GAA` transcribe into `UUU` and `UUC`.

That is incorrect for a DNA coding strand.

Those DNA sequences produce `AAA` and `GAA` RNA, respectively, and therefore different amino acids.

The example is correct when interpreted as the DNA **template strand** in the specified orientation. In fact, their Lean code uses these sequences to prove the template-strand theorem, while the coding-strand theorem uses a different pair.

So this is a mistake in the paper's explanation rather than evidence that its formal proof is incorrect.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://arxiv.org\&sz=32)

arXiv+1



### **B. The codon decoder has a questionable default**

This is the more interesting implementation problem.

The authors define all 64 standard RNA triplets, but their function also includes:

```
| _ => AminoAcid.STOP
```

This means an invalid sequence, such as a one- or two-nucleotide fragment, can be interpreted as a STOP codon.

The translation function groups nucleotides in chunks of three, potentially leaving a shorter final chunk.

Consequently, a malformed input can silently produce a biologically meaningful-looking STOP result rather than an error.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub



For a rigorously verified biological program, a better design would distinguish valid codons from invalid inputs at the type level, or return an explicit error.

This is exactly the kind of semantic issue the paper warns about.

### **C. Mutation constraints are incomplete**

The mutation function accepts any value of the general nucleotide-base type, including uracil, even when modifying a DNA sequence.

The authors prove that their replacement function preserves length, but that does not establish that its output is biologically valid DNA.

Similarly, out-of-range mutation indices can leave the sequence unchanged without reporting an error. The paper acknowledges the indexing issue.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://arxiv.org\&sz=32)

arXiv+1



### **D. The mathematics contains a minor overstatement**

Section 3.6 says a function has an inverse if and only if it is injective.

Strictly, a function needs to be **bijective** to have a two-sided inverse across its entire domain and codomain. Injectivity suffices for a left inverse under the usual conditions.

Their specific reconstruction theorem remains sensible; the general mathematical explanation should be more precise.

## **4. Relevance to Eidosoma's Cells simulator**

I think the connection is significant at the software architecture level, but much less direct at the level of biological modeling.

Cells uses mechanistic biological models, multiple levels of detail, and numerical simulation. Formal verification could provide an additional level of confidence in the rules that make up these models.

Here is how I would prioritize it.

| Cells subsystem                        | Potential formal verification                                 | Priority      |
| -------------------------------------- | ------------------------------------------------------------- | ------------- |
| Ion transport                          | Charge accounting, valid direction/sign conventions           | High          |
| Gap junctions                          | Equal-and-opposite currents between connected cells           | High          |
| Reaction networks                      | Stoichiometric conservation properties                        | High          |
| Model composition                      | Consistent interfaces and units                               | High          |
| Multi-scale/LOD transitions            | Conservation across transitions where applicable              | High          |
| Numerical solvers                      | Selected mathematical properties and bounded-error guarantees | Medium        |
| Protein folding and molecular dynamics | Whole-system correctness                                      | Low initially |

For example, consider two electrically coupled cells.

A gap junction permits current to flow between them. A basic mathematical requirement is:

\\[ I\_{A\rightarrow B}=-I\_{B\rightarrow A} \\]

If one cell loses charge through the junction, the other must receive the corresponding charge, assuming no additional charge-storage or transport mechanism is represented in that connection.

A formal specification could ensure that any valid gap-junction law respects this relationship.

This does not prove that the current has the correct magnitude, that the channel conductance is accurate, or that the biological model is realistic. Those require experimental evidence.

But it can eliminate entire classes of implementation mistakes.

### **A practical architecture for Cells**

**Biological Law Registry**

Explicit mechanistic assumptions, equations, parameters and scope

**Formal contracts**

Lean or other verification methods for selected invariants

**Empirical validation**

Wet-lab measurements, published data and calibration

**Cells simulation engines**

CPU/GPU execution, numerical tests and deterministic replay

The advantage is keeping two fundamentally different questions separate:

**Is the implementation faithful to its mathematical specification?** Formal methods can sometimes establish this conclusively.

**Is the mathematical specification faithful to nature?** This requires biological validation and carefully designed experiments.

I would introduce formal contracts for selected, high-consequence kernels rather than attempt to rewrite the entire Cells engine in Lean.

## **5. Final evaluation**

Conceptual and methodological value

8/10

Novel biological discovery

2/10

Depth of biological modeling

3/10

Value for verified scientific software

8/10

Practical relevance to Cells

7/10

My subjective assessment, not a published scoring system.

I consider this a useful early demonstration of applying theorem proving to biological software, rather than a major advance in genetic-code research.

The key opportunity for Eidosoma is not to prove obvious biological properties such as codon redundancy. It is to formalize selected **conservation laws, physical constraints, component interfaces and cross-scale consistency requirements** so that errors are caught before simulations are trusted.

And there's a particularly interesting implication for AI-generated scientific code: an AI agent could propose new biological models and their expected invariants, while a theorem prover independently checks the claims that are mathematically provable. Empirical validation would remain a separate requirement.

**My recommendation:** Worth studying as a software-verification approach. The next meaningful experiment would be to formally verify one small Cells ion-transport or gap-junction kernel, then compare the proven specification against the actual numerical implementation and biological validation data.

That would push this methodology substantially closer to real scientific value.
