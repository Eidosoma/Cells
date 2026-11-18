# Showing what cannot be seen: ideas, before anything is built

15 November 2026. Written for the user to choose from. Nothing in this note is built into
the viewer. The page with the sketches is `docs/ideas/invisible-quantities.html`.

The user's words: "explore how we can visually represent "invisible" things, like
electrostatic forces, voltage gradients, in an informative but also impressive visual
style in our 3D simulations. Have the agent explore this then come up with ideas before
starting building something, we want this modular and extendible and connect to the
Engine".

## The short answer

- **Voltage gradients can be shown today.** The saved runs hold one membrane voltage per
  cell at each record, and the junctions between cells. The gradient across a tissue is
  the difference between neighbours. Two ideas use exactly that (1 and 2 below).
- **Electrostatic forces do not exist in the engine as forces.** It has no force on a
  single molecule. What it has is the electrical push on each kind of ion, inside its
  transport laws, and the charge that a membrane voltage stands for. Both can be drawn
  truthfully from saved numbers (ideas 3 and 4).
- **Flows and energy are computed by the engine and not saved** by the runs the viewer
  has: fluxes through channels, pumps and junctions, the potentials inside and outside
  each cell, the energy ledgers (ideas 5 and 6 wait for them).
- **A field in the space between cells is not in today's runs.** Each cell's
  surroundings are held at 0 V there. The engine can resolve that space, but the viewer
  has no run that does (idea 8).
- **The design I recommend:** a quantity layer is data (which record, which mark, its
  scale, its legend); a mark is a small module (tint, relief, wedge, beads, arrows,
  stipple, glow, bands). A new quantity then needs no code, and a new mark needs one
  module. Five requests to the engine's run-view output follow from it.
- **What I would build first:** idea 1, voltage relief, with idea 2 on top of it. They
  need nothing from the engine and they answer the first of the user's two examples.

## 1. What is invisible, and what the engine has of it

"Engine has" means the model declares the field; the file and place are given. "Saved
today" was checked on one judged E07-v1 run (`definition.json` and `records.npz`) and on
the viewer's replays (`out/runs/`). I did not read the saved arrays of other experiments.

| Quantity | Engine has | Lives on | Unit | Saved in today's runs |
| --- | --- | --- | --- | --- |
| Membrane voltage | Simulated: `membrane_voltage_V` | each membrane (one per cell in the sheet) | V | **Yes.** `vm`, one value per cell and record. The viewer's replays carry it |
| Voltage difference between neighbours | Simulated: `junction_voltage_V` | each junction | V | Not saved. Exactly the difference of two saved voltages in these runs, because every cell's surroundings are held at the same potential |
| Potential inside and outside a cell | Simulated: `cell_potential_V`, `extracellular_potential_V` | cell; outside node | V | Not saved |
| Electric field in the space between cells | Outside nodes joined by faces, with potentials and fluxes across the faces. A network, not a continuous field | outside node; face | V per face (V/m needs distances) | **No.** In E07-v1 each of the 127 cells has its own outside node, a held bath at 0 V, and there are no faces |
| Ion concentrations | Simulated: `amount`, `extracellular_amount` | cell and outside node, per species | fmol (mM with the volume) | Yes in the run (`conc`, three species per cell). Not yet packaged in the replays |
| Ion fluxes | Simulated: `membrane_flux_fmol_s`, `junction_flux_fmol_s`, `face_flux_fmol_s`, `channel_flux_fmol_s`, `pump_cycle_rate_fmol_s`, `electrode_current_A` | membrane, junction, face, channel population, pump | fmol/s, A | Not saved |
| Open fraction of junctions and channels | Simulated state: junction gate, channel gates; availabilities | junction, channel population | 1 | Junctions yes (`gate`, `abundance`). Channel gates no |
| Charge on the membrane | Follows from the declared capacitance and the voltage | membrane | C | Derivable: capacitance and area are in the definition (0.05 F/m² in E07-v1), the voltage is saved |
| The push on each ion | The transport laws use the electrochemical potential, `R T ln(c) + z F V`; pumps report `pump_affinity_J_mol` | membrane, per species | J/mol (or mV) | Derivable from saved voltage and concentrations, with the bath's composition and the temperature from the definition |
| **Force on a molecule or a charge** | **Not in the engine** | | | |
| Energy spent and dissipated | Simulated ledgers: `membrane_`, `junction_`, `face_` and `channel_dissipated_energy_pJ`; `metabolic_power_pJ_s`; `energy_balance_pJ_s` | membrane, junction, face, channel | pJ, pJ/s | Not saved |
| Osmolarity, water, volume | Simulated in the water operator | cell | as the model declares | E07-v1 saves `osm` per cell. The water runs are not in the viewer |
| Tension, pressure, forces in a sheet | Simulated in the vertex model: area elasticity, line tension on each junction, perimeter contractility, and the force on each corner | cell, edge, corner | the model's own | The qualified run's files were not read. The run view does not carry moving shapes yet |
| Secreted signals | Simulated and numerically qualified (version 1) | cell and face, per species | amount | No run with it is prepared for the viewer |
| Fuel | Earlier model families: a finite pool. Composite model: held constant. The rework: shared species, planned | cell | | No |
| Arrival of an electrical wave | Excitable tissue is designed; its first milestone landed as validation code only | cell | s | No. Records are 10 s apart; a wave needs milliseconds |

Where each claim comes from, in the main checkout on 15 November 2026 (the note recorded no
revision; its engine paths are that day's, before the engine's two source moves of D188, whose
tables in the engine's `scripts/moves/` give each file's home since):

- The fields: `src/cells/models/surface_tissue.py` (`STATE_AXES`, `OBSERVATION_FIELDS`)
  and `src/cells/models/surface_kinetic.py` (`OBSERVATION_FIELDS`), which the tissue
  model `resolved_pump_tissue@3` inherits (`src/cells/models/surface_pump_v3.py`).
- The electrochemical potential and the junction voltage as a difference of two node
  potentials: `src/cells/models/surface_pump_v3.py` (the energy bookkeeping near the top,
  and `junction_heat_rate`).
- The space between cells: `docs/ARCHITECTURE.md`, "Communication and space":
  "Extracellular fields use their own grid, with explicit cell-to-field deposition and
  field-to-cell sampling. The field grid need not have one element per cell." The field
  solver on main takes at most 2,048 electrical nodes (`FACTORED_MAX_NODES` in
  `src/cells/numerics/surface_field.py`), and a wider interface is proposed with no code
  (`docs/FIELD_SOLVER_INTERFACE_DESIGN.md`).
- The vertex model's energy and forces: the opening of
  `src/cells/processes/vertex_mechanics.py`.
- Secreted signals: the status line of `docs/SECRETED_SPECIES_TRANSPORT_DESIGN.md`.
- What one run saved: `e07-v1-judged-20261113-01/runs/a-donor-fast-k1-d37-s0.6/seed1/`
  under the evidence folder: `definition.json` (127 cells, 127 outside nodes that are
  held baths at boundary potential 0 V, no faces, 342 junctions, 254 channels, four
  species, 310 K) and `records.npz` (`t`, `vm`, `conc`, `osm`, `abundance`, `gate`,
  `generation`, `regular`, `valid`).
- What the engine plans to write for the viewer: `docs/RUN_VIEW_DESIGN.md` (proposed, no
  code) and the requirement in `docs/ARCHITECTURE.md`, "Analysis and viewing" (D154).

So, of the user's two examples:

- **Voltage gradients:** yes, today, at the resolution of one value per cell. Finer than
  a cell, the engine has nothing: a cell is one well-mixed compartment with one membrane.
- **Electrostatic forces:** not as forces. The honest substitutes are the charge on the
  membrane (idea 4), the push on each ion (idea 3) and, when a run resolves the space
  between cells, the potential there (idea 8). Forces between charged molecules, as in
  pictures of protein surfaces, would be illustration from outside the engine.

## 2. How others show such things

Each source below was opened; the links are to the pages read.

| Technique | Good at | How it fails | Cost in the browser at our sizes |
| --- | --- | --- | --- |
| **Tint**: a colour on the thing itself | One level per cell or junction, read at a glance | Rainbow and red-green scales distort and exclude colour-blind readers ([Crameri, Shephard and Heron 2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC7595127)). Two tints cannot share one surface | Nothing: the viewer's replay already tints cells |
| **Relief**: height for a level | Plateaus, cliffs and slopes: the shape of a pattern, and its sharpness | Hides what stands behind a peak; exaggeration misleads unless a bar states it | Light: the cells are already instanced prisms |
| **Lines of equal value** (contours, isochrones) | Reading a value off a surface; arrival times of a wave ([openCARP, electrical mapping](https://opencarp.org/documentation/examples/02_ep_tissue/06_lats)) | Suggests detail between samples that the data does not have | Light |
| **Arrows and other glyphs** | A direction and a size at a few chosen places | Clutter and hidden arrows once there are many, worst in 3D (the survey of [Laramee and others 2004](https://diglib.eg.org/handle/10.2312/10081) treats arrows as the direct, and weakest, method) | Light when few |
| **Field lines, evenly spaced** | The course of a field across a plane | Density is a choice of the drawing, not of the data: lines must be placed evenly on purpose ([Kitware, evenly spaced streamlines](https://kitware.com/evenly-spaced-streamlines-2d)) | Moderate: lines are computed once per record |
| **Moving particles** | A steady flow: where it goes and how fast ([Cesium, GPU-powered wind](https://cesium.com/blog/2019/04/29/gpu-powered-wind/)) | Motion always reads as transport. Particles on a field that carries nothing lie | Moderate. Thousands of beads are instanced meshes; the example list of three.js r170 has instancing and graphics-card particle examples |
| **Flowing textures** (line integral convolution, [Cabral and Leedom 1993](https://history.siggraph.org/?p=118617)) | A dense picture of a whole field on a surface | Needs a field on a grid, and reads as noise when the field is coarse | Heavy to build; no ready three.js piece |
| **Shells of equal potential** | The reach of a charge in space: molecules are drawn with shells at ±1, ±5 or ±10 kT/e ([APBS with PyMOL](https://apbs.readthedocs.io/en/latest/using/examples/visualization-pymol.html)) | The chosen level decides what is seen ([Mura 2016](https://arxiv.org/abs/1606.03797) is a whole note on that confusion) | Moderate to heavy: three.js has a marching-cubes example |
| **Fog and volumes** | A quantity that fills space, and its fading | Hard to read a value from; hides what is behind it | Heavy on weak machines: three.js r170 has volume examples (`webgl_volume_cloud`, `webgl_volume_perlin`, `webgl_texture3d`); our checks run on software graphics, where they are slow |
| **Glow and halos** | A magnitude at a place, with drama | Reads as light or heat; needs a legend that says what it is | Light |
| **Potential painted on a surface** | Where a molecule is positive and negative: red through white to blue, from −10 to +10 by default ([ChimeraX, coulombic](https://plato.cgl.ucsf.edu/chimerax/docs/user/commands/coulombic.html)) | Belongs to single molecules with known charges, which the engine does not have | Not ours to compute |
| **Stress in a sheet of cells** | Tension as a landscape, with the directions of greatest stress ([Tambe and others 2011](https://pmc.ncbi.nlm.nih.gov/articles/PMC3135682)) | Tensors are hard for a lay reader; ellipses clutter | Light |
| **Value and doubt together** | Fading the colour where the value is unsure ([Correll, Moritz and Heer 2018](https://idl.uw.edu/papers/uncertainty-palettes)) | Two meanings on one colour interfere unless designed together | Light |

What makes such a picture both truthful and striking, as I read these:

- **One meaning for each visual channel.** Colour says one thing, height one thing, motion
  one thing. Mixed, the reader guesses.
- **Motion only for flow.** The wind maps work because particles show the direction of a
  real flow. On a quantity that is only a level, motion invents a transport.
- **The unit on the picture.** A bar in millivolts turns a pretty shape into a reading.
- **Say what is drawn from data and what is illustration.** Molecular artists use licence
  for lay audiences and say so ([Goodsell, Olson and Forli 2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC7230070)). The viewer's rule is stricter: what is simulated, modelled in aggregate,
  prescribed or only illustration is always said.
- **Real voltage patterns are already pictures.** A voltage dye made the frog embryo's
  "electric face" visible ([Tufts University, 2011](https://www.eurekalert.org/news-releases/851850)), and voltage indicators change brightness with the membrane voltage ([Bando and others 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6739974/)). A simulated sheet drawn as light or height on its cells is the same
  kind of picture, and a lay reader can be told so.

One clash of habits to settle: molecule pictures paint negative red and positive blue;
tissue and heart pictures usually paint the positive-going side warm. The sketches use
the second. Whichever is chosen, the legend carries the signs.

## 3. Ten ideas

Ordered by what they need. "Cost" is to build and then to draw.

### Works on today's saved runs

1. **Voltage relief** (sheet). Each cell stands as high as its membrane voltage; a
   depolarised patch is a plateau and the border between two states is a cliff.
   - *Technique:* height and the one-hue tint on the sheet's own glass cells; lines at
     chosen voltages (the experiment's own mark, where it has one).
   - *Data:* membrane voltage per cell, V, at every record. Saved.
   - *Honest by:* height repeats colour; a bar says how many millivolts a step is; no
     smoothing between cells; the layer's representation is the run's.
   - *Cost:* small; light.
2. **Junction drops** (sheet). A wedge on each junction, as wide as the voltage
   difference across it, pointing down the drop; a closed junction shows as a break.
   - *Data:* voltage per cell and each junction's open fraction. Saved. Exact as a
     difference only while every cell's surroundings share one potential; otherwise the
     engine's own junction voltage is needed.
   - *Honest by:* a wedge is a difference, not a current, so it never moves.
   - *Cost:* small; light.
3. **Push and pull on each ion** (cell). For each ion: the push of its concentration
   difference, the pull of the voltage, and what is left. It shows why potassium leaks
   out while sodium is held back from rushing in.
   - *Technique:* glass arrows through the membrane, in millivolts, one group per ion.
   - *Data:* voltage and concentrations (saved; concentrations need packaging), the
     bath's composition and the temperature (definition).
   - *Honest by:* the two parts are the terms of the engine's own law; an arrow is a
     drive, not a flow; the formula is in the legend. It is marked as derived.
   - *Cost:* small; light.
4. **Charge on the membrane** (cell). Plus and minus marks crowd the two faces of the
   membrane at rest and thin out as the cell depolarises; the bulk stays neutral.
   - *Data:* voltage (saved), capacitance and area (definition).
   - *Honest by:* the count is real, one mark for a stated number of charges; where a
     mark sits is illustration and is said to be.
   - *Cost:* small to medium; light.
   - *What it would teach:* how little charge a voltage is. In the E07-v1 definition a
     cell starts with a net charge of 1.28 pC, about 8 million charges, against the
     213 fmol of ions it holds: one ion in about 16,000 is unbalanced, and all of that
     sits at the membrane (about 24,000 charges per square micrometre at −78 mV).

### The engine computes it; runs must save it

5. **Ion traffic** (cell). Beads cross through each channel population and pump at the
   rate the engine computes, one hue per ion.
   - *Data:* `channel_flux_fmol_s`, `pump_cycle_rate_fmol_s`, per species. Not saved.
   - *Honest by:* channels are modelled as populations, so a bead is a token of a rate
     with a stated worth; no bead moves without a flux behind it.
   - *Cost:* medium; moderate.
6. **Where the energy goes** (sheet, cell). Dissipated power glows at junctions and
   membranes; pumps pulse as they spend fuel.
   - *Data:* the dissipation ledgers (pJ, differenced to pJ/s) and pump power. Not saved.
   - *Honest by:* a legend in pJ/s that says glow is not temperature.
   - *Cost:* small to medium; light.
7. **Signal fog** (sheet). A secreted signal spreads from its source and fades.
   - *Data:* the species' amount per cell and face over time. No run prepared.
   - *Honest by:* filled cell by cell as the model has it; rings between cells are
     marked as drawn.
   - *Cost:* medium; moderate (heavy as a true volume).

### Needs new output from the engine

8. **Field between cells** (tissue). Bands of equal potential and evenly spaced field
   lines in the fluid between cells, around a wound, an electrode or a barrier.
   - *Data:* potential at outside nodes with their positions; flux across faces. A run
     that resolves the space between cells, and its geometry in the run view.
   - *Honest by:* no finer than the model's nodes; absent where there is no potential in
     space.
   - *Cost:* medium to large; moderate.
9. **Tension web** (sheet). Edge thickness for tension, a two-hue tint from squeezed to
   stretched, arrows only where forces are out of balance.
   - *Data:* corner positions over time, tension per edge, pressure per cell.
   - *Cost:* medium; light.
10. **Wavefront** (sheet). The front of an electrical wave as a bright band, with lines
    of equal arrival time behind it and blocked cells drawn as blocked.
    - *Data:* voltage at millisecond steps around the event, or the engine's own arrival
      times. Excitable tissue is designed, not qualified.
    - *Cost:* medium; light.

**The order I would take:** 1 with 2, then 3 and 4, then ask the engine for what 5 and 6
need. 1 and 2 are the cheapest, use only saved data, and are the sheet's own story: a
written pattern and its border. Building 1 first also proves the layer design below with
one quantity on two channels.

## 4. A modular design, to discuss

### Three options

| | A. Layers and marks | B. One view per quantity | C. Fields as textures |
| --- | --- | --- | --- |
| What it is | A quantity layer is data: a record of the run, one mark, a scale, a legend. Marks are small modules | Each quantity gets a hand-made view | Every quantity is resampled onto a grid and drawn by general graphics passes |
| Adding a quantity | Data only, if its mark exists; one module for a new mark | New code each time | Data only, once the passes exist |
| Combining | One layer on each channel (colour, height, links, motion, glow, overlay) | Not possible | Free, and easy to overload |
| Honesty | Marks sit on the thing the engine computed them for | Depends on each view | A grid invents detail between cells |
| Cost | The first layer costs most | Even; never falls | Highest |

**I recommend A.** A mark from C can join later as one more module, when the engine has
a potential on a real grid.

### The layer, as data

```json
{
  "id": "voltage-relief",
  "label": "Membrane voltage",
  "quantity": { "record": "vm", "lives_on": "cell", "unit": "V", "kind": "level" },
  "mark": "relief",
  "channels": ["height", "colour"],
  "scale": { "from": -0.080, "to": -0.020, "ramp": "one hue", "show_as": "mV" },
  "representation": "as the run view states it for the record's layer"
}
```

- **`quantity`** names a record of the run view, or an exact arithmetic over records
  from a short fixed list (a difference across a link; a product with a constant of the
  definition; the rate of a cumulative ledger). A layer made that way is marked derived.
  The viewer computes no physics beyond that list.
- **`lives_on`** is a set of the run view: cell, membrane, junction, channel, outside
  node, face, corner, edge. A mark is drawn on that set's own geometry.
- **`kind`** says what sort of number it is (level, difference, flux, amount, power), and
  for a signed one which way is positive. Marks refuse kinds they would misdraw: beads
  take a flux and nothing else.
- **`channels`** are what the mark occupies. One layer per channel in a lens; switching
  one on switches off the other on that channel. At most three layers at once.
- **`representation`** comes from the run view's layer for the record: simulated,
  modelled or prescribed, with derived and illustration for what the viewer adds. The
  legend always shows it.
- **Where layers are listed:** in the viewer's catalogue, as the replay labels are. A run
  offers a layer when its view has the records and the geometry the mark needs. A new
  record from the engine then makes its layer appear with no new code.

### A mark, as a module

One file with four functions: build on a lens's sets, update with values at a time, give
its legend, dispose. It declares its channels, the kinds it accepts and the geometry it
needs. The lens gives it anchors: where a cell's top is, where a junction's middle is,
where a channel's form stands. Nothing else in the viewer changes when one is added.

### What the engine would be asked for

These are requests to the lead, not decisions. The proposed run view
(`docs/RUN_VIEW_DESIGN.md`) already gives sets with ids, records with unit, axes and
layer, each layer's representation, events and geometry from the builders. On top of it:

1. **Save what the model already computes, when a run asks:** the flux fields, the
   junction voltage, the two potentials and the energy ledgers. E07-v1's driver saved a
   reduced set; the fields exist.
2. **A direction for every signed record:** its two ends and which way is positive
   (inside to outside; sender to receiver). The view states units and axes; a sign is
   the one thing a flow still needs.
3. **Positions for outside nodes and faces,** where a world has them, as the builders
   give positions for cells.
4. **A short window at fine time steps** around a fast event. The view's time bases
   already allow several.
5. **The owner of each record down to the law.** With the modular rework (laws as
   declared pieces) and its levels of detail (a representation declared per mechanism,
   with an error budget), a layer could say what stands behind a number and how exact
   it is. Both are in development on a branch and not on main, so this is for later.

One more that can wait: physics the viewer would otherwise repeat (the push on each ion,
arrival times) could be written by the engine as observations of its own.

## 5. Open questions for the user

1. **Which ideas first?** My order is in section 3.
2. **How bold?** Relief, glow and beads can be strong or quiet. The sketches lean quiet.
3. **May motion stand for a rate?** My rule: something moves only where the engine gives
   a flux.
4. **Real runs only,** or also the cell view with example numbers, marked as
   illustration?
5. **Ask the lead for the five now,** or after the first two layers show their worth?
6. **Which colour habit for signed potentials:** warm for positive, as tissue pictures
   do, or red for negative, as molecule pictures do?

## What this note did not do

- It built nothing in the viewer and changed no file outside `docs/`.
- The inventory rests on the model's declarations and on one judged run's files. The
  saved arrays of the water, mechanics, secreted-signal and excitable-tissue runs were
  not read.
- The sketches use invented numbers. They show a manner of drawing, not a result.
