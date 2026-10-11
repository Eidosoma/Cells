# BIO-003 source-review attachment

Reviewed 2026-09-09. These are supplementary review sources, **not a revision
of the BIO-001 numerical dataset**. The original data and BIO-002 prediction
are unchanged. See the [pilot closeout](../../../reports/BIO003_PILOT_CLOSEOUT.md).

Bonzanni M, Payne SL, Adelfio M, Kaplan DL, Levin M, Oudin MJ (2020),
*Defined extracellular ionic solutions to study and manipulate the cellular
resting membrane potential*, Biology Open 9, bio048553.
[Article DOI](https://doi.org/10.1242/bio.048553).
The article and supplement are retained under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/),
with attribution here; neither file has been modified. No endorsement is implied.

| File | Source and reviewed scope | SHA-256 |
| --- | --- | --- |
| [article.xml](article.xml) | [Europe PMC full text](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC6994931/fullTextXML); Figure 3 caption, cell culture, electrophysiology and statistics sections | `41626ffe5917c4f225cb516e83fafdbe97cf7e01d4d61d43633a0511f13beb5b` |
| [biolopen-9-048553-s1.pdf](biolopen-9-048553-s1.pdf) | One-page Figure S1, text extracted and whole page visually inspected; [source package](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC6994931/supplementaryFiles) | `11cee59f29fb69d3668680d81e9a07540cbaee83bb6bc9771da21c579a024024` |

These files were recovered from the earlier BIO-001 download and checked
against its XML/package identities before copying here. The reviewed ZIP hash
is `3843e402c2b2e9a9e303eded5206c1e0f87b6708e24b4ece5e0495f896be73ef`.
Its inventory contains 20 image files and this PDF; the PDF has no embedded
attachments. The ZIP itself is not duplicated in this attachment.

Figure S1 contains temperature comparisons of resting voltage and optical dye
signal stability plots for two cell lines. It does not supply C1-C3 numerical
means/SEMs, experiment-level grouping, or an electrical recovery trajectory.
No new numerical values were digitized. Visual inspection by the same assistant
is not a second-reader verification of the original endpoint extraction.

Browser access to PMC/publisher pages remained unavailable. The local
hash-verified public-API source was readable. Bounded DOI/title/correction/data
searches on the review date did not locate a resolving correction or numerical
dataset; this is not proof such material does not exist elsewhere. No authors
were contacted and no private data were accessed.

PDF text extraction and rendering used PyMuPDF 1.28.2 installed solely into
a temporary review directory. It is not a Cells dependency; no package or
environment upgrade was made to the project.
