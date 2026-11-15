# Flux in the Cell view, and a better look at rest: ideas, before anything is built

15 November 2026. Written for the user to choose from. Nothing in this note is built into
the viewer. The page with the live sketches is `docs/ideas/flux-and-look.html`.

The user's words: "add one more research agent, how can we vizualize flux in the 3D cell
view? give me ideas, I want this to look cool, we will only use browsers on computers or
phones with good GPUs - we'd not want to show the flux iself by default, and maybe you
could slow it down, give me options - but also not in flux mode then maybe there could be
some nicer effects and textures in the cell scenes".

## The short answer

- **How flux is drawn.** Six styles were tried in one sketch: beads, trails, ribbons,
  pulses, a swarm, travelling light. **I would take beads**, since a bead can be counted
  and so can be given a meaning ("1 bead = 2 million ions"). Trails with bloom are the
  same beads at the bold strength. The swarm is the truest picture and belongs to a
  close-up of one channel.
- **Time.** Real fluxes are millions of ions a second through one kind of channel. Two
  honest knobs exist: what one bead stands for, and how much time is slowed. **I would
  open at true speed with a token, with a slow-down slider beside it**, and let the rate
  set how many beads pass, never how fast they go.
- **Off by default.** At rest nothing moves. **Selecting a part shows that part's flux;
  a Flux switch on the card shows all of it.**
- **Where the numbers come from.** First, **the looping run the engine makes of each
  species' cell**, which the user has asked the engine for (the lead's word to the
  coordinator on 15 November; logged as feature request FR-11; not yet in main's record
  when this was written). The Cell view of a species then shows a named run of that cell.
  For a species or a part with no loop yet, two forms of illustration remain, both marked
  and never on by default: typical values from a cited source, or direction only.
- **The contract** (`schema/QUANTITY_LAYERS.md`) needs its rule 7 replaced and three
  short additions. The exact words are in section 6.
- **The resting look.** Ten effects were tried in one sketch. **Five first: studio
  reflections, filmic light, soft translucency, contact shade, a drifting crowd.** They
  keep the approved look, add depth and life, and cost little. Bloom is kept for flux, so
  that switching flux on makes the cell light up. Glass that bends light is the one I
  would leave out.
- **Devices.** Everything proposed runs on WebGL 2, which the viewer uses today. WebGPU
  now runs in the current Chrome, Edge, Safari and (on Windows and Apple-silicon Macs)
  Firefox, and would add computing on the graphics card for very large swarms. Nothing
  in the first picks needs it. Whether a published page may use it could not be checked
  from here: the page tests it on the reader's device and says what it finds.

## 1. What could flow, and what the engine has of it

Read in the main checkout on 15 November 2026 (at `bd8f1e9f`), with the note to the lead
(`docs/ENGINE_NEEDS_FOR_QUANTITY_LAYERS.md`) and the inventory in
`docs/INVISIBLE_QUANTITIES.md`. Every flow below is a running total the engine keeps: the
amount moved since the start. The rate between two saved times is their difference
divided by the time between, which the viewer's contract allows as the derivation `rate`.

| What flows | The engine's record | Lives on | Where it is declared |
| --- | --- | --- | --- |
| Ions through each kind of channel | `channel_transferred`, by species | channel population | `src/cells/models/surface_pump_v3.py` (`STATE_AXES`) |
| Ions through the membrane as a whole | `membrane_transferred`, by species | membrane | `src/cells/models/surface_tissue.py` |
| What the pumps carry | `pump_cycles`, `calcium_pump_cycles`: cycles, with what one cycle moves in the layout | membrane | `src/cells/models/surface_pump_v3.py` |
| Exchange with neighbours | `junction_transferred`, by species | junction | `src/cells/models/surface_tissue.py` |
| Exchange between outside spaces | `face_transferred`, by species | face | `src/cells/models/surface_tissue.py` |
| Water | `water_transferred_pL` ("Cell to outside positive"), with `volume_increment_pL` | membrane; cell | `src/cells/models/operators/osmotic_water.py` |
| Secreted signals leaving and arriving | `exchange_moved_fmol` ("Export positive") | exchange route | `src/cells/models/operators/species_exchange.py` |
| Signals made and cleared | `turnover_produced_fmol`, `turnover_cleared_fmol`, `turnover_outside_cleared_fmol` | cell; outside node | `src/cells/models/operators/species_turnover.py` |
| Chemistry inside the cell | `reaction_produced_fmol`, `reaction_consumed_fmol` | cell | `src/cells/models/operators/species_reactions.py` |
| Fuel being spent | `metabolic_work_pJ`; pump cycles times what a cycle costs | membrane | `src/cells/models/surface_pump_v3.py`; fuel as shared species is in the rework, not on main |
| Energy lost as heat | `membrane_`, `channel_`, `junction_`, `face_`, `pump_dissipated_energy_pJ` | each element | as above |

Three things follow.

- **The engine has no speed of an ion and no single channel.** A channel on the map is a
  population with one flux. So a token can only stand for a number of ions per second
  through a kind of channel. Where each token is drawn, and how fast it travels, is the
  picture's choice and must be said to be.
- **Which way is positive is not declared for most of these.** Two of the operators above
  state it in a comment; the tissue family does not. The note to the lead asks for it
  (its request 2), and the contract already says that a signed record is drawn with a
  direction only where its sign is declared.
- **No saved run the viewer has carries these totals for a whole cell.** The judged runs
  kept slim records. That is why the first honest source is the engine's looping run
  (section 5).

## 2. Six ways to draw a flux

All six are in the first sketch of the page, on one piece of membrane with a sodium
channel, a potassium channel, a chloride channel in balance and a pump.

| Style | What it is | Reads well | Fails | With many fluxes at once | Cost |
| --- | --- | --- | --- | --- | --- |
| **Beads** | A token passes through the channel form. One bead stands for a stated number of ions | Countable, so the legend can give it a meaning. Direction is plain. Works in a still picture | A stream per channel turns into hail | One stream for each kind of channel, not each channel | Light: a few hundred instanced spheres |
| **Trails** | The same beads, each with a tail | Direction at a glance; the most striking with bloom | A tail's length reads as speed. Every tail must be one length | As beads, and brighter where streams cross, which could be read as more flux | Light to moderate: about six times the instances, plus bloom |
| **Ribbons** | A tube as wide as the rate, with stripes that move its way | Width is the rate, as in a flow chart; calm, exact at a distance | Looks like a pipe of fluid. The stripes' speed means nothing and may be read as if it did | Good: widths compare well | Light: one tube per stream |
| **Pulses** | Rings pass through a channel, more often for more flux | No clutter: each channel blinks at its own rate | Two blink rates are hard to compare; blinking tires | The best of the six | Light |
| **Swarm** | Ions jostle at random on both sides; most never cross; a few drift through | The truest: random motion with a small net drift. Looks alive | The net rate is hard to read off; needs a counter beside it | Thousands of dots everywhere would swamp the cell | Moderate: thousands of points moved on the graphics card |
| **Light** | The channel carries a travelling band of light, brighter for more | No tokens at all; beautiful on glass | Brightness is a weak measure. It takes the `glow` channel, which the energy layer needs | Good, but the two cannot show together | Light, plus bloom |

Why the swarm is the truest, and why it is still not my first pick. The open paper on
principles for molecular animation (Jantzen, McGill and Jenkinson 2024) puts it in three
of its twelve principles: molecules move through random collisions; they are in constant
motion and do not start and stop; and not every molecule crosses a barrier. A stream of
beads marching through a pore breaks all three: it shows purpose where there is chance.
The token keeps beads honest: a bead is said to be a count of a net rate, not an ion. The
swarm needs no such excuse, but it cannot be counted, so it suits a close-up of one
channel with the rate written beside it.

**Recommendation.** Beads as the `quiet` strength of the mark; trails with bloom as the
`bold` strength (the contract's rule 9 already makes strength a setting); the swarm for
the close-up of one selected channel; pulses when the whole cell is in view and for a
visitor who asks for reduced motion (then as a still row of chevrons).

Two rules for every style:

- **One stream for each kind of channel, spread over the forms drawn.** The engine gives
  one flux per population. Dividing it over the channel forms in the picture is
  illustration, and the legend says so.
- **A stream in balance shows nothing.** No net flux, no token. The swarm alone can show
  that ions are still there.

## 3. Time: "maybe you could slow it down"

A plausible small cell moves about ten to twenty million sodium ions a second through its
channels (the sketches use 18 million, invented). Nothing can show that one ion at a time
at true speed. The arithmetic has two knobs:

> beads a second on the screen = ions a second ÷ (ions in one bead × slow-down)

| Option | What the visitor sees | What the legend must say | Risk |
| --- | --- | --- | --- |
| **A token, true speed** | Each bead stands for many ions | "1 bead = 2 million ions" | None, if the number is always on the picture |
| **Slow motion the visitor sets** | A slider. Time stretches and a bead stands for fewer ions. Near a million times slower, one bead is one ion | "1 second here is 1 microsecond in the cell", beside the token | At strong slow-down the cell's own state hardly changes in the time shown. That is true, and worth saying on the picture |
| **A loop** | A short stretch of a run played again and again, with a bar that shows where in the loop one is | The loop's length in the cell's time, and how long it takes to play | The seam: the end must meet the start (section 5) |
| **On demand** | Nothing moves until asked; then a part shows its flux for a few seconds | The same token, on the pulse | A pulse may be taken for an event in the cell. It is the viewer showing a steady rate for a moment |
| **The rate sets how many** | More beads for more flux, all at one speed | "Speed stands for nothing" | When rates differ a thousandfold, one token cannot serve both: the token then needs steps, or a stream gets its own |
| **The rate sets how fast** | Evenly spaced beads that run faster for more flux | "Faster means more ions a second" | Speeds are hard to compare, and a fast bead looks like a fast ion. The engine has no speed of an ion |

**Recommendation.** Open at true speed with a token; a slow-down slider beside it, with
the token changing as it moves; the rate sets how many beads pass. The token is chosen so
that the busiest stream shows about ten beads a second, and is rounded to 1, 2 or 5 times
a power of ten so that it can be read. The loop becomes the clock as soon as the engine's
looping runs exist: then "1 second here is …" is the loop's own slow-down.

## 4. Off by default: how flux is switched on

| Way in | Before | After | Good and bad |
| --- | --- | --- | --- |
| **On selection** | The resting cell; nothing moves | Selecting a part (by its label or by clicking it, as today) shows that part's flux, and the panel gives the numbers | Calm; found by doing what a visitor already does; one part at a time |
| **Flux mode** | A switch on the card, off when the page opens | Every part the run has a rate for shows its flux, under one legend | The full picture and the busiest. The token must be chosen for the whole cell |
| **A burst on click** | The resting cell | A few seconds of flux at the clicked part, then rest | Playful and quiet; may be read as something the cell did |
| **On hover** | The resting cell | Flux under the pointer | No hover on a phone; movement under a passing pointer distracts. I would not |

**Recommendation.** Both of the first two: selection shows one part's flux; the switch
shows all. Decorative motion (section 7) stops while any flux shows, so that only data
moves. For a visitor who asks for reduced motion, flux opens as a still picture (pulses
drawn as chevrons, with the numbers), and plays only when asked.

## 5. Where the numbers come from

The contract says that something moves only where a rate stands behind it (rule 3), that
examples with invented numbers are marked and kept apart (rule 6), and that a layer fed
by a run is drawn where the run is shown, not on a species' cell in the Cell view, "which
is not a run" (rule 7). The user now asks for flux in the Cell view itself. Three honest
ways, in the order I would take them.

### First: the cell's own looping run

The lead told the coordinator on 15 November that the user has asked the engine for
looping replay packages of each species' cell (feature request FR-11): the full thing
after the engine's rework, with an interim loop of the planarian's cell first. The lead
has also accepted, for the run output's design, that a run to be shown keeps the standard
history (the amounts transferred and the energy dissipated per channel, pump, junction
and face) and declares each record's direction, kind and owner. This is the lead's word
to the coordinator; it was not yet in main's record when this note was written.

With such a run, the Cell view of a species is the picture of a named run of that cell.
What the picture says, always:

> Planarian cell · the engine's looping run *(its name)* · a loop of 2.0 s of the cell's
> time · slowed 3 times · 1 bead = 2 million ions

**What a loop must carry for each style.**

| Style | Records | How often |
| --- | --- | --- |
| Beads, trails, pulses | For each kind of channel and for the membrane, the amount of each ion moved in each interval; pump cycles in each interval, with what one cycle moves; which way is positive | Enough intervals to follow how the rates change: a few dozen in a loop |
| Ribbons, light | The same. They draw the rate itself, so a jump between two intervals shows as a step | As above; more where the rates change fast |
| Swarm | The same, with the amount of each ion on each side of the membrane, so each side's crowd is as dense as the run says | As above |
| Any | The loop's length in the cell's time; that its end equals its start, and how closely; the run's name, model and revision, and which cell it is | Once |

**How the end meets the start.** A running total never loops: at the seam it would fall
back from its last value to its first. Two things keep the picture whole:

1. The viewer never takes a difference across the seam. Every rate is the amount moved
   between two records that both lie inside the loop. So the package gives either the
   amount moved in each interval (which repeats cleanly), or its running totals with the
   closing record, one more record than intervals.
2. The state at the end equals the state at the start, within a tolerance the package
   states. Otherwise levels (a voltage, a concentration) jump at the seam as well. Making
   a run that closes is the engine's work; the viewer only refuses to loop one that says
   it does not.

### Second: typical values, as illustration

For a species or a part with no loop yet: numbers from a cited source, not from a run.
This is the user's earlier allowance: the viewer may draw illustrative machinery driven by
aggregate values, and must mark it as illustration. On the picture:

> Illustration: not a run · typical values for an animal cell *(source)* · 1 bead = 2
> million ions

It needs a source for each number, under terms that allow the number to be kept in the
repository, and a new rule in the contract. It is never on when the page opens, and it is
not offered for a part the species' file says the species lacks.

### Third: direction only

Which way each ion goes, and more or less of it in three steps, with no number: sodium
in, potassium out, the pump three for two. On the picture:

> Illustration: direction only · the number of beads stands for no rate

The weakest of the three and the easiest to mistake for data. I would use it only where
the second has no source.

**For a species the page calls proposed** (Syn3A, M. pneumoniae: "nothing of it is in the
engine"), only illustration is possible until the engine has a run of it, and the label
must keep saying so.

## 6. The change the contract would need

In `schema/QUANTITY_LAYERS.md`. The coordinator owns that file; these are the words I
propose.

**Rule 7, replaced:**

> **Drawn where the run is shown; in the Cell view only from that cell's own run.** A
> layer fed by a run is drawn in that run's replay: on the sheet, or on a close-up of one
> chosen cell's membrane, named with the run, the cell and the time. In the Cell view of
> a species it is drawn only from that species' own looping run, a run the engine made of
> that one cell and packaged to loop. The picture then names the run, says that it loops,
> and gives the loop's length in the cell's time and how much it is slowed. A species
> with no such run shows no run-fed layer in its Cell view.

**Rule 3, one sentence more:**

> A layer on the `motion` channel states its time on the picture: true speed, how much it
> is slowed, or the loop it plays; and what one token stands for.

**A new rule, only if the user allows illustration in the Cell view:**

> **Illustration in the Cell view is a class of its own, off when the page opens.** Where
> a species has no looping run, flux may be shown in its Cell view only as illustration,
> in one of two declared forms: `typical values`, from a cited source and not from a run;
> or `direction only`, where the count of tokens stands for no number. It carries
> "Illustration: not a run" on the picture and in the legend for as long as it is shown,
> never shares a picture with a run-fed layer, and is not offered for a part the species'
> file says it lacks.

**A new rule for decoration (section 7):**

> **Decoration never moves with a direction.** Motion that is not a layer (a drifting
> crowd, a shimmering membrane) has no net direction, stops while any layer on the
> `motion` channel shows, and stops for a visitor who asks for reduced motion.

One more thing the contract may want to say, from section 2: a stream is drawn once for
each kind of channel, and spreading it over the forms in the picture is illustration.

## 7. A better look when nothing flows

### The viewer as it is

Read in `src/core/stage.js`, `src/core/environment.js`, `src/core/materials.js`,
`src/lenses/cell.js` and `src/lenses/cell_parts.js`:

- One WebGL renderer with built-in edge smoothing, the screen's pixel ratio capped at 2,
  no tone mapping, and no finishing pass of any kind.
- Light from a sky and one sun; shadows are switched off in the Cell view.
- Glass is a standard material made transparent (the membrane at its own opacity, with a
  rim of light and more opacity toward the edges, added by a small shader hook).
- One set of surroundings to reflect: a pale dome with two bright panels, prepared once.
- The cytosol's crowd is thousands of still points; channels and pumps are instanced.

So the look is clean and cheap, and nearly everything below is new to it.

### Ten options

| Effect | What it adds | Cost on the graphics card | How it could mislead | On a weaker device | What the build needs |
| --- | --- | --- | --- | --- | --- |
| **Studio reflections** | Glass and wet surfaces catch large soft lights, with a little warm and cool, instead of a pale dome | None per frame: prepared once | A bright reflection can look like a mark: keep the lights soft and large | Unchanged | Nothing new |
| **Filmic light** | Highlights roll off instead of clipping; colours gain depth | Close to none | It shifts colours. Data marks and status colours stay out of it | Unchanged | One renderer setting; the natural colours checked again after it |
| **Soft translucency** | Organelles glow faintly at thin edges, as soft matter does | A few lines in the surface shader | Little | Unchanged | An addition to the existing shader hook |
| **Contact shade** | Soft darkening where parts meet and beneath them: the inside gains depth | One or two extra passes over the screen, at half size. Glass cannot take part: only solid parts | Darkness could be read as density: keep it gentle | Half size, or off | An add-on pass of three.js, or a small library, bundled; a depth texture |
| **Surface texture** | Folds of a mitochondrion, grain on the ER's sheets, pores on the nucleus | Noise in the shader, or small generated textures | Detail no data stands behind. It stays scenery, as the page already says | Unchanged | Nothing new |
| **Glass with depth** | The membrane bends what lies behind it and tints with its thickness | The scene is drawn a second time for the glass. Glass does not see other glass | Bending moves things from where they are, which hurts a labelled picture. At the scale of molecules light does not do this at all | Fall back to today's glass | The physical material of three.js; care with shells inside shells |
| **Depth haze** | Far parts fade toward the page's colour | None | Faded could be read as planned or absent: status stays in the dot beside the name | Unchanged | Nothing new |
| **Crowd drift** | The cytosol's crowd jostles slowly at random: the cell looks alive | None to speak of: points move in the shader | Motion could be read as flux. It has no net direction and stops while flux shows | Unchanged | The points' shader |
| **Membrane shimmer** | The membrane reads as a fluid sheet, not a hard shell | A few lines in the shader | A travelling ripple would look like a voltage wave. No waves: a slow flicker in place | Unchanged | The existing hook |
| **Bloom** | Bright edges and marks glow | Several blur passes at reduced size | Glow is a channel for data (the energy layer; the flux styles). At rest I would leave it off | Off | An add-on pass, bundled; a float or half-float target |

**Recommendation: five first.** Studio reflections, filmic light, soft translucency,
contact shade and a drifting crowd. Then surface texture, which costs little but adds
detail that is not data. Depth haze and shimmer are matters of taste. Bloom is kept for
flux mode. Glass that bends light I would leave out: the paper cited above lists
refraction, caustics and light rays among the effects that do not exist at the molecular
scale, and at the scale of a cell the bending still moves labelled things away from where
they are. A cheaper and safer way to give glass depth is to tint it by how much glass the
eye looks through, with no bending; the sketch does not show that variant.

**Two limits of the sketch.** Contact shade is faked there with soft shadows and a shader
term; the real pass costs more. Glass with depth uses the physical material directly; in
the real cell, with shells inside shells and a transparent crowd, it would need more
care than the sketch shows.

## 8. Devices, and what a published page can load

The user: computers and phones with good graphics cards.

- **WebGL 2 is the floor.** Everything above runs on it. Particles moved on the graphics
  card need float textures, which WebGL 2 on a good card has (the page reports it).
- **Where WebGPU runs** (web.dev, 25 November 2025): Chrome and Edge on Windows, macOS
  and ChromeOS since version 113; Chrome on Android 12 and later, with Qualcomm or ARM
  graphics, since 121; Safari on macOS, iOS, iPadOS and visionOS 26; Firefox on Windows
  since 141 and on Apple-silicon Macs since 145. Linux in Chrome, and Linux, Android and
  Intel Macs in Firefox, were in progress. I could not confirm what has shipped since.
- **What three.js offers.** Its documentation says the WebGPU renderer "tries to use a
  WebGPU backend if the browser supports WebGPU. If not, WebGPURenderer falls backs to a
  WebGL 2 backend." At the viewer's version, 0.170.0, the source has that fallback, and
  the renderer is a file of its own (`three.webgpu.min.js`) on cdnjs, the script host the
  page already uses (checked through the host's own list of files). Later versions are
  described by several blogs as ready for production; I did not verify that claim.
- **What it would add.** Computing on the graphics card as a first-class step (hundreds
  of thousands of particles without the detour through textures), and one shader
  language for both renderers.
- **What it would cost.** The viewer's materials are standard three.js materials with a
  small shader hook (`soften` in `src/core/materials.js`, through `onBeforeCompile`).
  The documentation of three.js says of that hook's companion method that it "can only
  be used when rendering with WebGLRenderer"
  (<https://threejs.org/docs/pages/Material.html>). Under the WebGPU renderer materials
  are written differently, so every such hook would be rewritten. Nothing in the first
  picks needs it. I would stay on WebGL 2, and write the particle step so that it can
  move later.
- **Inside a published page.** Not verified from here: the page runs in a locked frame,
  and I could not test that frame. The line at the top of the ideas page asks the
  reader's browser, inside that frame, whether WebGPU is offered and whether an adapter
  answers, and shows the result. In the server's headless browser it was offered and no
  adapter answered, which says nothing about a real device.
- **What the build needs.** The finishing passes (bloom, contact shade) are add-on
  modules of three.js under the same MIT licence. The page is built into one file with
  three.js loaded from cdnjs, so the add-ons would be bundled into the page. No new
  script host, and no second library unless the half-size contact shade is taken from
  one.
- **Frame rates.** The ideas page shows the reader's own frame rate beside each sketch.
  The pictures I checked were drawn in software on a server, which says nothing about a
  graphics card: I report no cost in numbers.
- **Reduced motion.** A visitor who asks for it gets every sketch paused on a still
  frame, and the same should hold in the viewer: flux as a still picture with numbers,
  and no decoration that moves.

## 9. What flux mode would ask of the engine, beyond the note to the lead

The note to the lead already asks for the standard history, a declared direction, a kind,
the owner down to the law, what a pump cycle moves, one identity per species, and two
small runs. Flux in the Cell view adds these. They are requests; the lead decides.

1. **A loop that closes.** Its last record equals its first, with the tolerance stated;
   and the amounts moved in each interval, or running totals with the closing record, so
   that nothing is differenced across the seam.
2. **Enough intervals in a loop** to follow how the rates change, and more of them around
   a fast event.
3. **For each kind of channel, how many channels it stands for and how open they are**
   (the engine has the abundance and the gate), so that a stream can be spread over the
   forms drawn and the panel can say what one channel passes on average.
4. **Water, secreted signals and fuel as amounts moved**, if they are to flow too: the
   records exist (section 1) but the note to the lead's table lists only ions, energy and
   one secreted species' amounts.
5. **The run's own name for the label:** which model, which revision, which species and
   which cell, and the loop's length in the cell's time.

Not asked: where on the cell each kind of channel sits. The engine has one membrane per
cell, so placement stays the picture's choice, and the page says so.

## 10. What others do, and what was taken from each

Every page below was opened on 15 November 2026. No figure is copied.

- **Truth in molecular motion.** Jantzen, McGill and Jenkinson, "Design principles for
  molecular animation", *Frontiers in Bioinformatics* 2024 (CC BY):
  <https://pmc.ncbi.nlm.nih.gov/articles/PMC11371733/>. Twelve principles, among them:
  molecules move through random collisions; they are in constant motion; attraction is
  local, and "distant molecules flooding toward a target invokes agency"; not every
  molecule crosses a barrier; "light-based effects are not observed at a molecular
  scale" (caustics, refraction, distortion, light rays); the cell is crowded. Taken: the
  swarm as the truest style; the token as what keeps beads honest; no net direction for
  decoration; no bent light in glass.
- **How viewers take in animation and still pictures.** Pokojná and others, *PLoS One*
  2023 (CC BY): <https://pmc.ncbi.nlm.nih.gov/articles/PMC10627439/>. Non-experts
  preferred a detailed still picture and found a fast video hard to follow; slowing down
  was among their suggestions. Taken: a still form for every moving mark, and slow motion
  as a control in the visitor's hand.
- **Animation that made cells look alive.** WEHI.TV, the biomedical animation team led by
  Drew Berry: <https://www.wehi.edu.au/wehi-tv/>. Taken as the bar for "looks cool":
  crowded, jostling, softly lit.
- **Whole cells of molecules in real time.** cellVIEW (TU Wien), in a games engine:
  <https://www.cg.tuwien.ac.at/cellview>; in the browser, the Mol* Mesoscale Explorer:
  <https://molstar.org/me/>. Taken: instancing and levels of detail carry very large
  scenes; an illustrative style helps shape be read.
- **A readable look without photorealism.** Goodsell's Illustrate: "cartoony colors and
  outlines, and soft ambient shadows": <https://ccsb.scripps.edu/illustrate/>. Taken:
  contact shade first; outlines as a later option.
- **Particles moved on the graphics card.** Wellons, "A GPU Approach to Particle
  Physics", 2014: <https://nullprogram.com/blog/2014/06/29/> (state kept in pairs of
  textures; positions read in the vertex shader). The wind map built on it, "up to 1
  million wind particles at 60fps": <https://github.com/mapbox/webgl-wind>. The same
  idea in three.js: its `GPUComputationRenderer` add-on (MIT),
  <https://github.com/mrdoob/three.js/blob/r170/examples/jsm/misc/GPUComputationRenderer.js>.
  Taken: how a large swarm would be built on WebGL 2. The sketch's swarm is simpler: its
  points are moved by a formula in the vertex shader and keep no state.
- **Glass in real time.** The physical material of three.js (transmission, thickness,
  attenuation; "a higher performance cost, per pixel"):
  <https://github.com/mrdoob/three.js/blob/r170/docs/api/en/materials/MeshPhysicalMaterial.html>.
  drei's transmission material, which lets glass see other glass at the price of "an
  additional render pass of the scene":
  <https://github.com/pmndrs/drei/blob/master/docs/shaders/mesh-transmission-material.mdx>.
- **Cheap translucency.** Barré-Brisebois and Bouchard, GDC 2011, as used by the
  subsurface example of three.js:
  <https://colinbarrebrisebois.com/2011/03/07/gdc-2011-approximating-translucency-for-a-fast-cheap-and-convincing-subsurface-scattering-look/>.
- **Contact shade at half size.** N8AO, whose half-resolution mode is "a great way to get
  a performance boost (generally 2x-4x) at the cost of some quality":
  <https://github.com/N8python/n8ao>.
- **WebGPU.** Where it runs: <https://web.dev/blog/webgpu-supported-major-browsers>. Its
  renderer in three.js: <https://threejs.org/docs/pages/WebGPURenderer.html>.
- **Reduced motion.** <https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion>.

One source could not be opened: the Mapbox article on the wind map answered with a
refusal. Its repository's own description was read instead.

## 11. What was checked on the page, and what was not

- **Checked:** the page was opened in the server's headless browser, wrapped as a
  published page is. No script error and no shader error was reported with every style
  and every look option switched on. Pictures were looked at for all four sketches in
  light and dark at wide size, for all four at phone width in dark, and for the top of
  the page and the section on numbers; the page has no sideways scroll at 1440 or 500.
- **Seen only as stills.** Every sketch was looked at as a still frame, never moving: the
  pictures are single frames, and the server draws in software far too slowly to judge
  motion. That beads, trails, pulses, the swarm and the light bands move as described is
  what the code does, not what I watched. The reader is the first to see them move.
- **Not measured:** any frame rate. Software drawing says nothing about a graphics card.
- **Not checked:** the page inside the published frame (fonts, WebGPU, the script host's
  answer there); a real phone; pointer and keyboard turning of the sketches; reduced
  motion, beyond reading the code path.
- **Two things in the sketches are stand-ins,** as the page says beside them: contact
  shade (soft shadows and a shader term, not a screen pass) and the swarm (points moved
  by a formula, with no state kept on the graphics card).

## 12. Open questions for the user

1. **Which style?** Beads, with trails as the bold strength, and the swarm for a
   close-up: or another?
2. **How should time be shown when flux opens?** True speed with a token and a slider
   beside it: or slowed from the start?
3. **How does flux come in?** On selection, with a Flux switch for all: or a switch only?
4. **May the Cell view show illustration** where a species has no looping run yet, marked
   as such? If not, flux in the Cell view waits for each species' loop.
5. **Which resting effects first?** The five named above: or others from the ten?
6. **May anything move at rest?** The drifting crowd and the shimmer are decoration. They
   stop for reduced motion and while flux shows. Or should the resting cell be still?
7. **Should water, signals and fuel flow too,** or ions only at first?
