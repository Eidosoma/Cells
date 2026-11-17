# Origin of life in the viewer: GARD, the options, and a recommendation

Ideas and options for the user, 16 November 2026; the view the user chose is now built standing alone,
with a preview page (see "Status", below). **Nothing of GARD is in Cells' engine yet.** The engine's
GARD design note is **on main, decided on 16 November 2026** (`docs/GARD_DESIGN.md`, D192; first read
on its branch `gard-design` at `e75b4b1f`), and GARD is built in step 4 of D194's order; this note and
the page beside it follow its names and its run records, and mark what they take from it. The page,
[`docs/ideas/origin-of-life.html`](ideas/origin-of-life.html), draws each option live from a small toy
that it runs when it opens. The toy follows GARD's rules as the preprint and the original papers print
them; it is not Cells' engine, not the preprint's code and not its runs, and nothing it shows is a
finding.

The user, 16 November 2026: "add another agent to look into adding a new "species" type Origin of life
and the first one GARD, which is one theory we need for an origin of life simulation GARD, which our
plastic heredity paper was based on - we'll ask lead also do look into it". The engine's lead, the same
hour, named what the viewer could show: assemblies growing and splitting; their compositions, with the
similarity H and composomes; lineages across fissions, and the inheritance threshold (H > 0.9, F12); and
reminded that nothing of GARD is in the engine, so whatever is drawn is labelled so.

## Decided

The user answered the nine questions of section 6 on 16 November 2026, after the options page was
published: "get adviser in on this then go on your recommendation on all of those", and, a moment
later, "be ambitous". The visualizer session's advisor reviewed the answers and reversed none. So,
as recommended:

1. **"Origin of life" is a new heading in the species switch, and a GARD assembly is a model system,
   not a species**: a new kind of entry, with four levels of its own (Molecules, One assembly,
   Population, Lineages).
2. **The assembly is drawn as a micelle**, labelled as the picture's choice, with the cluster on a
   phone and where less motion is asked for.
3. **A GARD run plays in the entry's own view**; the Experiments view lists GARD runs and opens them
   there.
4. **The clock counts fissions**, with molecule by molecule at the slow end and no "true speed". It is
   the page's one time control with a second ladder of speeds, not a control of its own.
5. **The 0.9 line is drawn only on the comparison of a parent with the daughter that carries on.**
   Anywhere else a threshold is the picture's choice and is said to be.
6. **Composomes are named only where a run or its analysis names them.**
7. **The options page's toy does not enter the built viewer.** The viewer draws saved runs.
8. **One lineage first, populations later.**
9. **Where the engine runs both forms of its kernel, the viewer shows the pair under one clock**, each
   labelled with the law it ran, and says nothing of which is right. (Asked again on 16 November,
   late evening, whether the preview should show the two already, the user: "yes we'll wait for the
   real runs but great to have everything ready". See "Status".)

**How "be ambitious" is read** (the visualizer session's reading, not the user's words): the whole
view is built now, and not only the entry with an empty view while the engine's first GARD run is
awaited.

- **The view is built standing alone first**, as the Laws library was: the assembly, the composition,
  the similarity, the map, the lineages and the clock, with the page's look.
- **Until the engine has a GARD run, the view plays an example run of invented numbers**, made by a
  tool in this folder and saved as a small file, and marked as an example on the picture and in the
  legend, in the way the example sheet of the replays is marked today. It is not a run of Cells' engine
  and not the preprint's runs, and nothing it shows is a finding. This goes one step past answer 7 as it
  was recommended (which named such a file for tests only), and is the one point of this reading that
  the user may want to turn down.
- **The view reads a run through a contract of the viewer's own.** The engine's GARD design note
  was then proposed, on a development branch (it is now on main, decided: "Status"), so no code here
  binds to its record names: a table says which of its records each field would be read from, and an
  adapter is written when the engine's first run exists.
- **The entry, its contract and its place in the switch are designed together with the cell-type
  contract** (`docs/CELL_TYPES_DESIGN.md`): species, cell type and model system change the same reader
  and the same switch, so they are one change. It is wired into the page when the files it shares with
  work in progress are free.

## Status, 16 November 2026, late evening

- **The entry reads "Designed, not modelled"** (`data/models/gard.json`, under `schema/ENTRIES.md`):
  the engine's design note is a tracked file of main, decided (`docs/GARD_DESIGN.md`, D192), and GARD
  is built in step 4 of D194's order. Nothing of it is in the engine.
- **The two forms of the law, in D192's words** (`docs/DECISIONS.md`, D192, "The reversibility
  finding, as checked"): in a closed two-type world, the preprint's single-event kernel generically fails Kolmogorov's cycle criterion (a rank-one catalysis matrix is the exception); the original authors' kernel is not established either way; the preprint's vector-Poisson contracts were not tested; the preprint's driven runs are not affected; the pair-consistent form is exactly reversible. The engine builds both forms, and its first experiment measures the difference. The viewer uses these words and no others, and shows no comparison of
  the two forms on invented numbers.
- **The pair of forms is ready for the engine's runs** (the user: "yes we'll wait for the real runs
  but great to have everything ready"): a run states its form (`law.form`, with the engine's own name
  in `law.engine_name` once it has one) and its world; the view offers the two side by side only for
  two real runs of the engine, of one world, by one set of rules, one of each form, and never for an
  example (`schema/ASSEMBLY_RUN.md`, "The two forms of the law, side by side"). Tests hold it on a
  test's own two made-up runs, which no page carries.
- **What the engine's runs will be** (D192: an exact stochastic simulation, one molecule an event;
  abstract assemblies over a generic ideal-mixing phase; a dense lognormal matrix with about a hundred
  types as each world's data): the contract carries each without change (its table "What the engine's
  runs will be").
- **The assembly is drawn as lipids in water** (the user, 16 November 2026, late evening: "so for the
  origin of life GARD simulation, let's make that one visually amazing - for example lets simulate the
  self assembly of the lipids (visuall for now but maybe law later), and the different chemicals
  seeping in and out, and the split, let's use nice water and lipid 3D elements and textures"). The
  run gives which type joins or leaves and when, the composition, each fission and how it divides the
  molecules; everything else (how a lipid looks, moves and packs, the water, the free molecules, every
  size) is the picture's own, and the picture says that no law of Cells computes how the lipids move
  and pack. A head's form and colour say its type; the micelle stands on a phone and with less motion
  too (this replaces the cluster of answer 2 there); the founder gathers from the water at a run's
  start, the one exception to the rule of motion, said so on the picture. The preview page is built by
  `node tools/build_view_page.mjs lineage` (`src/standalone/lineage.*`).

## On the map's page, 17 November 2026

- **The view is on the map's page.** Choosing GARD in the species switch (or `entry=gard` in the
  address) shows it in the first tab's place, named "Origin of life" ("Life" on a phone, which keeps
  the bar to one row). It plays the marked example as the page opens it, after the founder has
  gathered, and it stands for a visitor who asks for less motion and with `still=1`.
  - Its levels are the page's rail, under "Level". Its clock is the page's one timeline.
  - Its legend and note are the page's legend. Its similarity is a select on the page's card.
  - It is mounted by `src/lenses/lineage_entry.js` and one line in `src/ui/model_views.js`.
- **The example's mark stands at the first place free of the page's cards**, under the bar, at every
  level and window size. On a phone it wraps to stand beside the card.
- **The pair of forms stays unseen.** No page carries two real runs, so the page offers no pair. A
  check-only scene with a test's own two made-up runs holds it (`tools/check_origin.mjs`, `CASE=pair`).
- **On a phone at the Lineages level**, the lineage is shorter and seen from the front, under the
  page's card, and the assembly leaves it the picture.
- **The micelle stands everywhere, on a phone and with less motion too.** Answer 2 had the
  cluster there. Asked again once the micelle was built to stand still, the user left it to
  the coordinator (17 November 2026: "You decide"), who chose the micelle: it is the picture
  the view was built for, and it costs the same to draw as the cluster (the same draw calls
  and triangles by turns in one page on the project's graphics card; no phone was measured).
  Version 13 of the map had shipped it before the answer and Versions 14 and 15 the cluster.
  The choice is one line, `CLUSTER_WHERE_SMALL_OR_STILL` in `src/lenses/lineage.js`, and
  either packing can be chosen on the card.
- **Contact shade is left to the Molecules level.** At the Lineages level it cost a frame about
  1.5 ms on the card, and kept the page just under 60 frames a second at 1400 by 900.

## The protocell, 17 November 2026

The user looked at the view on the map and sent two slides of their own public deck as the
direction for its look (the deck of 10 November 2026, kept outside the repository,
pages 12 and 13, "GARD Origin-of-Life Simulator" and "GARD Growth and Division"; nothing of the
slides is in the repository):

> I'm not asking for this level of Lipid simulation but still something that has the lipid
> assembly then small molecules moving in and out

and, on what moves:

> yes, so the lipid [assembly] self assembles then the molicules move in and out of it, the 90 or
> whatever we use in our GARD

So:

- **The view opens on a protocell**, a third packing beside the micelle and the cluster (the
  picture's choice, as they are): a closed shell of the run's lipids, a molecule each, in two faces,
  heads to the water outside and inside with the tails between. Its two faces are drawn as soft
  glassy surfaces (the picture's own, no molecule), so that its 40 to 80 lipids read as one shell; a
  bilayer of so few molecules could not otherwise close. Its near side is drawn see-through, so its
  inside shows and every molecule stays on the picture.
- **The molecules seen moving in and out are the run's own,** of its own types: each one drawn
  coming in is a join of the run, each one going out a leave. They are seen at every speed, not only
  molecule by molecule: no more than a cap fly at once, and where a growth's pace would put more in
  flight, one in N is drawn in flight and the legend says N. The joins come in on one side and the
  leaves go out on the other, as on the slide. First the founder gathers, then the exchange is seen,
  in the user's order. No solute that is not a molecule of the run is drawn, and nothing carries a
  chemical's name.
- **The catalytic network inside** is read from the run's world: for the types the protocell holds,
  the links are its table's factors (which type speeds which), the strongest drawn. It changes as the
  types held change and never pulses with a join, since the run does not record what helped one.
- **At a fission** the shell draws in at its waist into two protocells, each with the lipids the
  run's split gives it and its own network; the daughter that carries on stays, the other drifts off
  into the haze.
- **What is the picture's own** is said on the picture and in the legend: "No law of Cells computes
  how the lipids move and pack: the shell, the paths in and out, the water and every size are the
  picture's own. Which molecule joins or leaves, and in what order, is the run's."
- **`CLUSTER_WHERE_SMALL_OR_STILL`** now says whether a phone and less motion get the cluster (true)
  or the protocell like everywhere else (false, as it stands).

What follows is the note as it was handed over, unchanged but for these sections and the lines
that state the engine's note's status.

**The record, the same day.** GARD's build in the engine started on 17 November 2026
(`docs/CURRENT_PLAN.md`); nothing of it is on main yet. By D197 GARD is one law set, kept only for
comparison, and the origin-of-life engine is to be Cells' own, with laws from physical chemistry; its
design note, `docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md`, is proposed; its first choices were decided on
17 November (D199). The entry's words and
notes say so (`data/models/gard.json`). That note proposes vesicles, a bilayer round a lumen, as the
engine's first assemblies, dividing at shear events into two or more: when such runs exist, this view
will need a vesicle's picture for them.

## In short

- **Recommendation.** Add a heading "Origin of life" to the species switch, with "GARD assembly" as a
  new kind of entry, a model system and not an organism, with four levels of its own: Molecules, One
  assembly, Population, Lineages. Build its view in this order: the composition strip and the
  similarity at each fission, under one time control that counts fissions (C, D left, G); then the
  assembly drawn as a micelle, labelled as the picture's choice (B); then the lineage tree (F); then
  the carpet of similarities and the map of compositions (D right, E). The toy stays on the ideas page:
  the built viewer draws the engine's GARD runs and runs no GARD of its own.
- **What GARD is.** An assembly holds integer counts of 100 molecule types (the engine's note names
  them t000 to t099). A fixed matrix β of 100 × 100 numbers, drawn from a log-normal distribution,
  says how much each type inside speeds the joining and leaving of each other type; β and the held
  reservoir are the environment, never the assembly's state. The assembly grows one molecule at a time
  to 80, splits in two, and one daughter continues the lineage. Similarity H is the cosine of two count
  lists. The preprint calls a fission inherited when H between the parent just before it and the
  daughter that carries on is above 0.9; F12 asks for a break and then three inherited fissions in a
  row within twelve. The original papers add composomes (self-preserving mixes that recur) and
  compotypes (groups of them, found by clustering). GARD has no shape, place, membrane, charge or
  real-life clock.
- **What each sketch would read** (the engine's note, section 5, proposed): the composition strip,
  wheel, tape, map and carpet read `assembly_count` (an `amount` on [row, species, assembly], saved at
  each fission's two rows); the similarity at each fission reads the run's `boundary_similarity` (a
  `level`, [fission, 2]); the tree reads the fission table and its `fission`, `retirement` and `birth`
  events, with `time.event_rows` giving the parent before the split; the list's joins and leaves are
  differences of the `cumulative` totals `joined_total` and `left_total`. The 0.9 marks, F12 and
  compotypes come from the analysis in `validation/gard/`, not from the run.
- **H: read the run's own wherever it has one.** The inheritance verdict rests on it, a value of
  exactly 0.9 is a break that a rounded copy must never decide, and the note already checks H from two
  rows against `fission_similarity`. The page works out only the comparisons the run does not save (the
  carpet; birth against grown), as a fifth declared derivation, which changes
  `schema/QUANTITY_LAYERS.md` rule 1.
- **What the page needs beyond the note's defaults:** the event trace (saved only on request) or
  cadence rows, to draw a molecule arriving; and the analysis's outputs saved where the viewer can read
  them. Both are questions for the lead (section 7).

## What changed after reading the engine's note

The page and this note were first written before the engine's note existed, from the preprint and the
open papers. On reading it (`e75b4b1f`):

- **Names follow the note:** molecule *types* (t000 to t099) for what the first draft called kinds;
  *fission* for the event and *split* only for the partition; *slots* for a population's places; the
  note's entities (assembly, reservoir, lineage, world), laws and operators.
- **The run-view mapping is now the note's section 5,** in place of my own proposal: `assembly_count`
  in place of a "counts" record; lineage-cumulative totals; `boundary_similarity` on the fission table;
  the fission table and the replacement slot idiom in place of a set with lifetimes; `time.event_rows`;
  no `resets`. The page's "What the engine would be asked for" became "What a run would save, and what
  each sketch reads".
- **The comparison "its sibling" became "the parent against the other daughter",** because the run's
  record holds H for the parent against each daughter.
- **Inheritance and F12 are the analysis's,** in `validation/gard/`, so the threshold is the analysis's
  constant, not a `mark` the run writes.
- **The toy's kernel is said to be the preprint's single-event form,** `cells.member_catalysis_at_state@1`
  in the note's names (which the engine builds for the reference comparison; D192's words are in
  "Status").
- **The entry's card moves to `proposed`,** since the design note is now a tracked file on a
  development branch (and later to `designed`, when the note reached main: "Status").
- **New questions for the lead** (section 7), and one for the user (question 9: the two kernel forms
  side by side).
- **The population tree's 24 lanes are the note's slots:** a fission writes its two daughters into the
  parent's slot and the removed member's slot, which is how the toy's lanes were already laid out.

## Refs read

- **The engine, main** `b92b4c2b` (16 November 2026), read with `git show`: `README.md` (the research
  goals, the preprint's DOI), `docs/SCIENTIFIC_BASIS.md` (S01; "The preprint's GARD catalytic matrix and
  reservoir are fixed environmental constraints"; the F12 definition with its strict threshold),
  `docs/ARCHITECTURE.md` ("GARD, Boolean regulation, and continuous biochemical equations need explicit
  contracts if supported"), `docs/DECISIONS.md` (D007). No GARD code anywhere on main; checked again at `dced303a` the same
  evening, with the same result.
- **The engine, `gard-design` at `e75b4b1f`**, `docs/GARD_DESIGN.md` (PROPOSED, docs only): its summary,
  sections 1, 2.2–2.3, 4, 5 and 8, read with `git show`, never checked out. (At `3c10b833`, when I began,
  the branch held no note.)
- **The viewer**, branch `visualizer` at `288cc04b`, with other agents' uncommitted files read around:
  `README.md` (Species, Experiment replays, Quantity layers, Rules the map keeps), `schema/SPECIES.md`,
  `schema/RUN_VIEW.md`, `schema/QUANTITY_LAYERS.md` (rules 1 to 12), `docs/CELL_TYPES_DESIGN.md`
  ("Decided" and section 5), `tools/lib/species.py` and `src/lenses/cell.js` (the fixed level list),
  `src/replay/player.js` (the speed ladder), and the earlier ideas pages, chiefly
  `docs/ideas/laws-library.html` for its form.
- **The preprint**, *Plastic heredity: Predicting and steering how inheritance breaks, returns, and
  persists*, doi:10.5281/zenodo.22143269, as it resolves on 16 November 2026: version 5.0 (CC BY 4.0;
  the Zenodo PDF, whose checksum matched the record's). The engine's record cites version 2.3 (S01); the
  F12 definition it states is the one version 5.0 prints. Read: "In brief", the introduction, the
  reader's guide, "Common experimental framework", Figure 4's caption, "Plastic heredity and the
  composome debate" and Appendix F.
- **The open GARD papers** (full text from Europe PMC, each CC BY 4.0): Lancet, Zidovetzki and
  Markovitch 2018 (the review, PMC6073634); Gross, Fouxon, Lancet and Markovitch 2014 (PMC4357159);
  Markovitch and Krasnogor 2018 (PMC5813963).
- **Segrè, Ben-Eli and Lancet 2000** (PNAS; free to read, no licence stated): the publisher's page
  answered 403, Europe PMC holds no full text of it (500), and a direct download of its PubMed Central
  page was refused by the session's permission check, so that route was not tried again. Its PubMed
  Central page was read once, before that, through the fetch tool's summary only. **Nothing here rests
  on it alone**, and its summarised numbers are not used. (The engine's note read it, and reports its
  numbers.)
- **Vasas, Szathmáry and Santos 2010** (PNAS): not read; its argument is given as the preprint states it.

The downloads (the preprint's PDF, the three papers' XML and the text made from them) are in
`out/scratch-origin/`, which git ignores; nothing of them is copied into the repository.

## 1. What GARD is

### 1.1 As the preprint states it

From its "Common experimental framework" and Appendix F (all six of its principal versions):

| Part | The preprint |
| --- | --- |
| State | An integer composition x over 100 types; mass N = Σ x<sub>i</sub> |
| Start | Mass 40, 40 distinct types drawn uniformly without replacement |
| Catalysis | One 100 × 100 matrix per catalytic environment, β<sub>ij</sub> = exp(−4 + 4Z<sub>ij</sub>), Z standard normal, diagonal kept; reused for every lineage and future in that environment |
| Rates | b<sub>i</sub> = 1 + (βx)<sub>i</sub>/N; join a<sup>+</sup><sub>i</sub> = k<sub>f</sub> ρ<sub>i</sub> N b<sub>i</sub>; leave a<sup>−</sup><sub>i</sub> = k<sub>b</sub> x<sub>i</sub> b<sub>i</sub>; k<sub>f</sub> = 10<sup>−2</sup>, k<sub>b</sub> = 10<sup>−4</sup> |
| Reservoir | Constant and uniform, ρ<sub>i</sub> = 0.01, no depletion and no feedback from the assembly |
| Growth and split | Grow toward mass 80; then split. The six versions differ in the update (simultaneous Poisson batches, or single molecule events in proportion to every rate), the overshoot past 80, the split (each type binomial with p = 0.5, exactly 40 without replacement, or an exact-size hypergeometric split) and which daughter carries on (the first, the second, or either at random). Version T2-02: single molecule events, an exact-size hypergeometric split of ⌊N/2⌋ to the first daughter, the first daughter carrying on |
| Similarity | H(x, y) = x·y / (‖x‖‖y‖) |
| Inheritance | At each fission, I<sub>t</sub> = 1{H(P<sub>t</sub>, D<sub>t</sub>) > 0.9}: the parent just before the fission against the daughter that carries on. 0.9 itself is a break. Growth between fissions is not thresholded, and successive daughters are not compared |
| F12 | Within the next twelve fissions, a break and, strictly after it, three inherited fissions in a row. It needs no return to the old composition |
| Strict F32 | A break followed within 32 fissions by eight inherited daughters, all 28 pairs of them above 0.9, all at most 0.85 from the old pre-break parent |
| What is fixed | The reservoir, and the matrix except during imposed network interventions; neither is written or inherited by the assembly |
| Composomes | Not used by its endpoints; it states that it ran no clustering, no assignment to attractors and no test of recurrence; mapping its episodes onto compotypes is named as a next test |

### 1.2 As the original papers state it

- **The rate equation** (Gross and others 2014; Markovitch and Krasnogor 2018): dn<sub>i</sub>/dt =
  (k<sub>f</sub> ρ<sub>i</sub> N − k<sub>b</sub> n<sub>i</sub>)(1 + Σ<sub>j</sub> β<sub>ij</sub> n<sub>j</sub>/N),
  the same propensities as the preprint's, run by a stochastic simulation (Gillespie's algorithm in
  Markovitch and Krasnogor). ln β<sub>ij</sub> is normal with mean −4 and standard deviation 4; k<sub>f</sub>
  = 10<sup>−2</sup>, k<sub>b</sub> = 10<sup>−4</sup>, ρ<sub>i</sub> = 10<sup>−2</sup>, N<sub>max</sub> = 100 and
  N<sub>G</sub> = 100 there (80 in the preprint).
- **Split** at N<sub>max</sub> into two of N<sub>max</sub>/2. "Single-lineage mode": one daughter, picked
  at random, is followed and the other discarded (Gross and others 2014; Markovitch and Krasnogor 2018).
- **Populations**: a chemostat seeded with 1,000 random compositions, kept at one size by a Moran process,
  run for 50,000 single growth processes (Gross and others 2014). The engine's note words the step as a
  fission that removes a member at random, which is the rule the page's toy uses.
- **Composome**: a run of faithfully replicating assemblies, each closely like the one before it and the
  one after it (Gross and others 2014), compared when both are at N<sub>max</sub> (Markovitch and
  Krasnogor 2018). The review: a compositional
  quasi-stationary state, kept over several growth–split cycles by homeostatic growth (growth that keeps
  the proportions). No numeric threshold for "highly similar" is given in what I read.
- **Compotype**: a group of similar composomes, found by k-means clustering (with the k of highest
  silhouette), represented by its centre of mass and read as a GARD species (Markovitch and
  Krasnogor 2018, one to six per matrix in 10,000 runs; the review says one to seven).
- **The carpet**: the review's figure 3d draws H between the compositions at every pair of times for one
  assembly over 2,000 growth–split cycles (N<sub>G</sub> = 100, N<sub>MAX</sub> = 80); squares along the
  diagonal are composomes, and patches off it their similarity to one another.
- **The map**: the review's figure 2b draws a lineage's walk in the first three principal components of
  the 100-dimensional composition space.
- **Size**: composomes need N<sub>MAX</sub> ≤ N<sub>G</sub>; with 100 types they appear only in assemblies
  the size of micelles; a small vesicle 0.2 µm across would hold about 10<sup>6</sup> molecules, and GARD
  at such counts has not yet been simulated (the review).
- **Space**: the assembly is taken as well stirred, with no structure in space (the review).

### 1.3 Where they differ, and how the page keeps them apart

- **Two comparisons are both called H.** The preprint's is across the fission (parent before, the
  daughter that carries on) with a strict threshold. The papers' carpet compares grown assemblies across
  whole generations, with no threshold. On the page the 0.9 line is drawn only on the first; a ring of
  pairs above 0.9 on the carpet is offered as the picture's choice and is off at first.
- **Composomes** are the papers' and need a clustering method; the preprint uses none. The page clusters
  nothing.
- **N<sub>max</sub>** is 80 in the preprint and 100 in the papers read. The toy uses 80.
- **The preprint's reference 1** gives the 2000 paper four authors; Europe PMC's record gives three. The
  engine's note raises the same point with the lead (its question 6).

### 1.4 What GARD does not have

No shape, size in space, membrane, place or neighbours; no charge, voltage, energy or chemistry beyond β;
a fixed reservoir and matrix; no clock of real life. Whether GARD assemblies can evolve open-endedly is
disputed (Vasas and others 2010; the reply of Markovitch and Lancet 2012 and the review), and the
preprint sets the exchange out. So every shape, place and motion in a picture of GARD is the picture's
choice, and is labelled so.

### 1.5 In the engine's design note (on main, decided, D192)

- **Entities:** an *assembly* (integer counts over the species, a carrier key, an event counter; no
  volume, area or charge in the abstract option); the *reservoir* (held activities ρ and the matrix β:
  layout, never state); a *lineage* (its fission table and cumulative ledgers; one continuing assembly,
  or a fixed population of K slots); a *world*.
- **Species:** a declared type family `t000` to `t{N_G−1}`, label only.
- **Laws:** `cells.reservoir_exchange@1`; the catalysis factor in two forms,
  `cells.member_catalysis_at_state@1` (the published evaluation) and `cells.member_catalysis@1` (a
  second form, "pair-consistent", which the note proposes beside it).
- **Operators:** `cells.size_threshold_fission@1` (split `binomial` or `exact_fraction`),
  `cells.daughter_continuation@1` (`first`, `second`, `uniform`); later `cells.population_replacement@1`
  (a Moran step) and recorded interventions.
- **Observables:** H at each fission in the engine; F12, F32, composomes and compotypes in
  `validation/gard/`.
- **Clock:** nominal; the natural clock is the fission count.
- **Recommended:** exact single-molecule events; abstract assemblies first, declared so that vesicles
  in the physical world can bind the same laws later; dense log-normal β at 100 types; both kernel
  forms, with the published one for the reference comparison (the preprint's T2-02).
- **The two forms of the law, in D192's words:** in a closed two-type world, the preprint's single-event kernel generically fails Kolmogorov's cycle criterion (a rank-one catalysis matrix is the exception); the original authors' kernel is not established either way; the preprint's vector-Poisson contracts were not tested; the preprint's driven runs are not affected; the pair-consistent form is exactly reversible. The engine builds both forms, and its first experiment measures the difference (D192).

## 2. What a run would save, and what each sketch reads

From the engine's note, section 5 (on main, decided, D192):

| Record | Kind, axes | Saved | Read by |
| --- | --- | --- | --- |
| `assembly_count` | `amount`, [row, species, assembly], molecules | At each fission's two rows; at cadence rows if declared | B, C, D (carpet, birth against grown), E |
| `joined_total`, `left_total` | `cumulative` since the lineage began, never restarting | Yes | C's list: joins and leaves per fission |
| `discarded_total` | `cumulative`: material leaving with daughters not followed | Yes | B, as a count |
| `boundary_similarity` | `level`, [fission, 2]: the parent against each daughter | Yes | D, left; the list |
| The fission table | `fission_time`, `fission_slot`, `fission_parent`, `fission_daughters`, `fission_followed`, `fission_split`, `fission_similarity` | Yes | B's split; F |
| Events | `fission` at the slot, `retirement` of the parent, `birth` of the followed daughter; the other daughter born and retired at once; `time.event_rows`: the row at a fission's time holds the parent before it | Yes | F; the clock's steps |
| `occupant`, `generation` | `level`, [row, assembly] | Yes | F |
| The event trace | A diagnostic table: time, type, ±1; about 62 per fission | On request only | B and C, molecule by molecule |
| `join_rate`, `leave_rate`, `catalytic_factor` | `rate`, `level` | On request only | None of these sketches |
| `exchange_heat_kT`, `fission_work_kT` | `cumulative`; the heat declared non-monotone | Yes | None yet; the viewer's energy layer could show each fission's cost |
| β, ρ | The environment: arrays beside the definition | Yes | A's molecules level |
| Inheritance, F12, compotypes | Analysis in `validation/gard/` | By the analysis | D's marks, E's composomes |
| Shape, place | None in the abstract option | — | `space` null; the picture's shape is its own |

**H.** Read the run's `boundary_similarity` wherever it exists, and work out only the rest from
`assembly_count`. The reasons: the inheritance verdict rests on the run's own number; a value of exactly
0.9 is a break, and a copy rounded for drawing (the replay packs float32) must never decide it; and the
note already makes H from the two rows equal to `fission_similarity` a check, which the viewer would
repeat at every fission. Working H out is a fifth derivation beside `difference`, `rate`, `charge` and
`potential terms` (rule 1 of `schema/QUANTITY_LAYERS.md`, a closed list), so the contract changes.

**The viewer works out, and says so:** shares; the other daughter as the parent less `fission_split`, as the note defines it;
joins and leaves per fission as differences of the totals; H for pairs the run does not save; the map's
layout. **Never the viewer's:** the rates, which molecule joins next, the inheritance verdict, F12, and
composome clustering.

**Beyond the defaults, the page needs:** the event trace, or cadence rows, to draw molecules arriving;
without them, B and C step from the daughter at one fission to the grown parent at the next and say that
the growth between was not saved. And the analysis's inheritance marks, F12 windows and compotype
assignment, saved where the viewer can read them beside the run.

**Where the run view does not fit yet**, by the note's own list (its §5.3, for the view's owner): fission
events from the run's fission table, not a schedule; the fission table named as an event record; a
nominal time unit; and the writer's first version accepting no family but the existing composite.

**Sizes.** A lineage of 100 fissions at two rows each: 200 × 100 counts, about 40 kB as 16-bit integers,
with the fission table beside it; the event trace adds about 6,200 entries. A population of 1,000 over
50,000 fissions would be saved in parts or thinned, and the run would say which.

## 3. Where "origin of life" fits in the viewer

| | (i) A species file with a new group | (ii) A new kind of entry (recommended) | (iii) Experiments only |
| --- | --- | --- | --- |
| The heading | Free: the switch reads its headings from the files | The switch learns a second kind of entry | None |
| The levels | The fixed list (`tools/lib/species.py` `LEVELS`, `src/lenses/cell.js`) needs `molecules` and `cell`; GARD would be drawn as a cell | Its own fixed list: molecules, assembly, population, lineage | — |
| The contract | `taxon`, `organism` and `cell` are required | Shares the species file's identity, sources, licence classes and `modelled` blocks; drops organism, taxon and cell | — |
| Truth | Calls an assembly a cell | Says what it is | True, but hides it from the switch the user named |
| Cost (my estimate) | About 1 day, and a wrong picture | About 2 to 3 days | About 1 day, with the adapter |

A cell type (`docs/CELL_TYPES_DESIGN.md`) does not fit: a cell type belongs to a species and is a cell.
What a species and a GARD entry share is the top of that note's table in its section 5 (identity,
sources, licence classes, facts); what they do not share is everything about a cell.

**What its card says of the engine.** I would say `proposed`, now that the engine's design note is a
tracked file on a development branch; that is a choice, since the cell types' decision waited for a note
on main before calling a cell type designed. The line would read "nothing yet; a design is proposed, on a development branch, not on main
(16 November 2026)", with the record's one sourced fact on main (the preprint was built on GARD,
`docs/SCIENTIFIC_BASIS.md`). `modelled` only when the record says a registered GARD model exists.
(Since the note reached main, decided, the card reads "Designed, not modelled": "Status".)

**Levels.** Molecules (the hundred types and β), One assembly (the droplet, molecule by molecule),
Population (many assemblies at once, in a fixed number of slots), Lineages (generations across fissions).
A visitor arriving on the entry sees the card and "One assembly"; the Protein atlas and the Cell view's
parts have nothing for it and say so.

## 4. The options

Each is drawn live on the page, with what the visitor sees and does, what it reads, its cost, how it
holds for one assembly and for thousands, and how it works on a phone, with less motion, and without 3D.

| | Option | Reads (the engine's note) | Cost (my estimate) |
| --- | --- | --- | --- |
| A | The entry: "Origin of life" in the switch, the card, four levels, β at the molecules level | None; β for the molecules level | 2–3 days |
| B | One assembly, one bead per molecule, growing and splitting: micelle (pick), cluster, vesicle (shown to say why not: 80 molecules cannot make one) | `assembly_count`, `fission_split`, `fission_followed`; the event trace to draw each molecule | 2–3 days |
| C | Composition: strip (in type order, as long as the assembly is large), wheel, tape (after Markovitch and Krasnogor's "GARD tapes") | `assembly_count`; `joined_total`, `left_total` | 1–1.5 days |
| D | Similarity: H at each fission with the 0.9 line (also the parent against the other daughter, and birth against grown, with no line); the carpet of grown assemblies | `boundary_similarity`; the analysis's marks; `assembly_count` | 1–1.5 days |
| E | Composomes: a 3D map of compositions with the lineage's trail; names a composome only where the analysis does | `assembly_count`; the analysis's compotypes | 1.5–2 days |
| F | Lineages: one lineage as a spine with stubs; a population of 24 in 24 slots (the first daughter keeps the parent's slot, the second takes the removed member's, as the note records it) | The fission table and its events; `occupant`, `generation` | 2–3 days |
| G | Time: one control for all of it, counting fissions per second of watching and molecule by molecule; no "true speed" | The `fission` time base; the event trace for molecule by molecule | ½–1 day |

All of it: about 10 to 14 agent-days, of which A, C, D's left half and G are about 4 to 6, and the
adapter for the engine's GARD runs 1 to 2 more once a view of one exists. The engine's own estimate for
its four milestones is 20 to 29 agent-days (its §7.3).

**Colour.** Three leading types wear colour (blue, orange, aqua), each also with a shape (diamond, square,
triangle; in 3D octahedron, cube, tetrahedron) and its name; the other 97 types are grey circles
(spheres in 3D), so no coloured type shares a shape with the grey. The palette check
(`validate_palette.js` of the data-visualisation skill, with Machado and others' 2009 simulation) passes
six of the viewer's hues for neighbours in a fixed order, but only three when any two can sit side by
side, as beads in an assembly do: six fail (protan ΔE 3.2 light, deutan 1.4 dark). Hence three. The first grey (#9aa8b6, #6f8297 in
dark) was too close to the blue and the aqua in dark (normal vision ΔE 12.4 and 13.5, below the floor of
15), so neutral greys replace it: #b0b5ba and #c3c8cd light, #4f565e and #5d646b dark, each at least ΔE
9.3 (colour-blind) and 17.3 (normal) from every hue. Aqua on the light page, and orange and aqua on the
darker stage tone, are below 3:1 contrast with the surface; what relieves it is that no colour is read
alone (a shape on every mark, a name in every legend, the list of counts). Counts and H use one violet
ramp, faint to strong, so that no type's hue means a number. The record of the
check is `out/scratch-origin/palette-check.txt`.

## 5. Recommendation and order

1. **The entry (A)**, as a new kind of entry beside species, with an honest card.
2. **The core of a run** on the engine's first GARD run: the strip (C), H at each fission read from the
   run (D, left), the one clock (G). 2D, cheap, true to the preprint's own measure; works on a phone and
   as a list.
3. **The assembly as a micelle (B)**, with the cluster as its plain form; molecule by molecule only where
   the run saved its event trace.
4. **The tree (F)**, for one lineage, then for a population when the engine adds one.
5. **The carpet and the map (D right, E)**, once runs are long enough to show stretches and returns;
   composomes named only where the analysis names them.
6. **No toy in the viewer.** Tests use a small fixture of invented numbers, marked "Example: invented
   numbers", as the example sheet is (rule 6 of `schema/QUANTITY_LAYERS.md`).

## 6. Questions for the user

Each with my recommended answer.

1. Should GARD stand in the species switch under a new heading "Origin of life", as a model system and
   not a species? **Yes, as a new kind of entry with its own four levels.**
2. Which shape should the assembly have: micelle, cluster or vesicle? **The micelle, labelled as the
   picture's choice, with the cluster on a phone and with less motion.**
3. Should a GARD run play in the entry's own view, or in the Experiments view? **The entry's own view,
   with the Experiments view listing GARD runs and opening them there.**
4. Should the time control count fissions rather than seconds? **Yes: fissions per second of watching,
   with molecule by molecule at the slow end and no "true speed"; the engine's note also takes the
   fission count as GARD's clock.**
5. Should the 0.9 line be drawn only on the parent-to-followed-daughter comparison, as the analysis
   defines it? **Yes; elsewhere a threshold is the picture's choice and is said to be.**
6. Should composomes be named only where a run or its analysis names them? **Yes: the map shows where a
   lineage stays and names nothing itself.**
7. Should the page's toy ever enter the built viewer? **No: the viewer draws the engine's runs, and its
   tests use a marked fixture of invented numbers.**
8. Should one lineage come first and populations later? **Yes: it is the preprint's mode and the
   engine's first, and the engine adds populations later.**
9. When the engine runs both forms of its kernel side by side, should the viewer show a matching pair of
   runs under one clock? **Yes, each labelled with the law it ran, and nothing said of which is right.**

## 7. Questions for the engine's lead

1. Will a run made to be shown save the event trace for one lineage, or rows at a cadence, so that the
   assembly can be drawn molecule by molecule? Without either, the view steps from fission to fission.
2. Will the analysis in `validation/gard/` save its inheritance marks, F12 windows and compotype
   assignment where the viewer can read them beside the run, under which names, with its threshold
   stated (above 0.9, equality a break)?
3. Will the fission table be named in the run's view as an event record (the note's §5.3, point 2), so
   that the viewer reads fissions from it rather than from JSON events?
4. Which word will the time base state for nominal time?
5. May the viewer's energy layer draw `exchange_heat_kT` (non-monotone: a single event can lower it) and
   `fission_work_kT` for each fission, and with which words for their signs?
6. When both kernel forms run, will each run's view name the law it ran in `run.engine_models`?

**Two notes for the lead's sources, offered rather than asked:**
- The Zenodo PDF of version 5.0 (downloaded, checksum matching the record), which the note says it
  could not compare, agrees with the values its §1.1 gives: β = exp(−4 + 4Z) with the diagonal kept; k<sub>f</sub> =
  10<sup>−2</sup>, k<sub>b</sub> = 10<sup>−4</sup>, ρ = 0.01 held; mass 40 of 40 distinct types to 80;
  T2-02 with direct single-molecule events, an exact-size hypergeometric split of ⌊N/2⌋ and the first
  daughter.
- The note lists Lancet, Zidovetzki and Markovitch 2018 as refused and Gross and others 2014 as not
  retrieved. Both are open in full text at Europe PMC (PMC6073634, PMC4357159), CC BY 4.0, which is where
  I read them.

## 8. The page's toy

A small GARD-like simulation in the page's own script, run once when the page opens (about 15 to 80 ms
for 120 fissions in node on this machine; 0.4 to 0.6 s in the headless browser here) and then replayed
by every sketch under one clock.

- **From the sources:** 100 types; β<sub>ij</sub> = exp(−4 + 4Z<sub>ij</sub>); the boost, join and leave
  propensities with k<sub>f</sub> = 10<sup>−2</sup>, k<sub>b</sub> = 10<sup>−4</sup>, ρ<sub>i</sub> = 0.01;
  the start at 40 molecules of 40 types; growth to 80 (Appendix F); single molecule events in proportion
  to every propensity, an exact half drawn without replacement, the first daughter carrying on (the
  preprint's version T2-02); H and the strict 0.9 (the preprint); a population kept at one size by
  removing a random other assembly at each fission (Gross and others 2014).
- **Its kernel is the preprint's single-event form:** the factor b<sub>i</sub> at the current state for
  a join and a leave alike (`cells.member_catalysis_at_state@1` in the note's names). The engine builds
  it for the reference comparison, beside the pair-consistent form, its own law (D192); the toy offers
  only the preprint's form, and the page says so without judging it.
- **The page's own:** the seed (16, picked from 30 tried because its picture shows long inherited
  stretches, breaks and a return; seeds differ widely); the one
  matrix it draws; 120 fissions; waiting times, used only to order the population's events; a population
  of 24 that takes three of its fissions for each of the lineage's.
- **Not:** Cells' engine, the preprint's code or its runs. No statistic of it is shown, and the page says
  so at every sketch.
- `out/scratch-origin/toy.js` is the toy; `try_toy.mjs` and `carpet_ascii.mjs` ran it in node to choose
  the seed; `parts/`, `tools/` and `assemble.mjs` make the page; `shoot_page.mjs` takes the pictures.

## 9. What was checked, and how

The handover (`out/handover/origin-of-life.md`) gives the browser runs' results: stills of the viewport,
light and dark, wide and 400 px, with less motion and without the 3D library, through the project's
browser lock on cores 12 to 15 with their second threads. The sketches are drawn by software WebGL
there; no frame rate could be measured.

## 10. Uncertain

- The 2000 paper was read only through a summary, and is not used here.
- "Highly similar" in the papers' composome definition has no number in what I read; the preprint's 0.9
  is its own and applies to the fission.
- The cost estimates are mine.
- The engine's note is decided (D192) and not built; its names and records may still change as it is
  built.

## Sources

1. Cells, `docs/GARD_DESIGN.md`, the engine's GARD design note: on main, decided on 16 November 2026
   (D192, read at `fa19d80c`); first read on its branch `gard-design` at `e75b4b1f`.
2. *Plastic heredity: Predicting and steering how inheritance breaks, returns, and persists*, preprint,
   version 5.0, doi:10.5281/zenodo.22143269, CC BY 4.0, read 16 November 2026.
3. Segrè D, Ben-Eli D, Lancet D (2000) Compositional genomes: prebiotic information transfer in mutually
   catalytic noncovalent assemblies. PNAS 97:4112–4117, doi:10.1073/pnas.97.8.4112. Free to read, no
   licence stated; read only through a summary, not used.
4. Lancet D, Zidovetzki R, Markovitch O (2018) Systems protobiology: origin of life in lipid catalytic
   networks. J R Soc Interface 15:20180159, doi:10.1098/rsif.2018.0159, CC BY 4.0.
5. Gross R, Fouxon I, Lancet D, Markovitch O (2014) Quasispecies in population of compositional
   assemblies. BMC Evol Biol 14:265, doi:10.1186/s12862-014-0265-1, CC BY 4.0.
6. Markovitch O, Krasnogor N (2018) Predicting species emergence in simulated complex pre-biotic
   networks. PLOS ONE 13:e0192871, doi:10.1371/journal.pone.0192871, CC BY 4.0.
7. Vasas V, Szathmáry E, Santos M (2010) Lack of evolvability in self-sustaining autocatalytic networks
   constraints metabolism-first scenarios for the origin of life. PNAS 107:1470–1475,
   doi:10.1073/pnas.0912628107. Not read.

Numbers are taken with a citation; no text, figure or data file of any source is copied into the
repository.
