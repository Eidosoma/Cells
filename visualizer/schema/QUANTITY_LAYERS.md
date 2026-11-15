# Quantity layers: showing what cannot be seen

Status: **fixed for the viewer, 15 November 2026**, before the building. The user asked
for ideas first ("explore how we can visually represent "invisible" things, like
electrostatic forces, voltage gradients, in an informative but also impressive visual
style in our 3D simulations … we want this modular and extendible and connect to the
Engine"), saw ten (`docs/INVISIBLE_QUANTITIES.md`, and the page of sketches), and chose:
"Lets do them all except wait with 8. 9. and 10." So seven are built: voltage relief,
junction drops, push and pull on each ion, charge on the membrane, ion traffic, where the
energy goes, signal fog. The field between cells, the tension web and the wavefront wait.

A voltage, a charge, a flow or a store of energy cannot be seen. A **layer** draws one of
them onto something the viewer already shows, from numbers a run saved.

## Three things, kept apart

- **A record** is an array a run saved. The run's view declares it
  (`schema/RUN_VIEW.md`): its `id`; what it `lives_on` (`cell`, `junction`, `membrane`,
  `channel population`, `pump population`, `face`, `outside node`, `route`, `world`); its
  `unit`; its `kind` (`level`, `amount`, `cumulative`, `rate`); for a signed record its
  `sign` (what positive means: from what, to what); its `owner` (the model, operator or
  law that computed it, as the run's definition names it); how its layer of the engine is
  represented (`simulated`, `modelled`, `prescribed`); and its times.
  - A `route` is one declared route of an operator that carries a species across a
    membrane; it lies on its membrane.
  - The two ends of a `sign` are named by the roles of the record's set, as the engine's
    run view names them: `inside` and `outside`, `sender` and `receiver`.
  - A `cumulative` record may say that it only grows (`monotone`: the ledgers of
    dissipated energy), or that it restarts where an operator retires a slot (`resets`,
    with the laws that do so).
- **A layer** is data, a few lines:

```json
{
  "id": "voltage-relief",
  "label": "Membrane voltage",
  "quantity": {"record": "vm"},
  "mark": "relief",
  "channels": ["height"],
  "scale": {"from": -0.080, "to": -0.020, "unit": "V", "show_as": "mV", "ramp": "one hue"},
  "says": "Each cell stands as high as its membrane voltage."
}
```

- **A mark** is a small module of code that draws one kind of sign on the geometry a view
  has: `tint`, `relief`, `wedge`, `arrows`, `stipple`, `beads`, `stream`, `glow`, `fog`. It
  says which visual channels it takes, builds itself for a run, moves to a time, makes
  its legend, and takes itself down.

A new quantity with a known mark is data alone. A new mark is one module. Nothing else in
the viewer changes.

## Rules

1. **Saved, or worked out by a declared rule; never physics of the viewer's own.** A
   layer's numbers are a saved record, or one of the derivations below, and a derivation
   is always shown as "worked out by the viewer from …". The viewer never computes a law
   again (a flux from a permeability, a gate, a reaction rate). What a layer would need
   beyond this is asked of the engine (`docs/ENGINE_NEEDS_FOR_QUANTITY_LAYERS.md`). The
   list is closed; adding to it changes this contract:
   - `difference`: a level at one end of a junction less the level at the other. For
     voltage this equals the junction's own voltage only where both cells' surroundings
     share one potential: where a run kept the engine's own readout of the junction
     voltage or of each cell's potential, the layer reads that record and derives
     nothing;
   - `rate`: a `cumulative` record at one saved time less the same at the one before,
     divided by the time between: a mean over that interval, and said to be one. The
     rate shown at a record is that of the interval which ends there, and the picture
     names the interval; a run's first record has none. More on rates below;
   - `charge`: capacitance times voltage, with the capacitance and the area as the run's
     definition gives them. The charge is counted on a stated piece of membrane, and one
     mark stands for a stated number of charges; where each mark sits is illustration;
   - `potential terms`: for one ion at one membrane, the two terms of the engine's own
     electrochemical potential difference, R T ln(c inside / c outside) and z F V, and
     their sum, from the saved concentrations and voltage and the definition's
     temperature and valence (the engine's `electrochemical_potential`, in
     `src/cells/processes/electrochemistry.py`). Shown in millivolts, each divided by z F.
     Where a run saved amounts, a concentration is the amount over the volume of its
     compartment.

   A derivation reads its inputs as the run had them. A value that an operator of the
   run may change (a volume, a capacitance or an area, the composition of a held bath) is
   read from the definition only where no operator of that run changes it; otherwise the
   run must have saved it over time, or the layer is listed as one the run cannot feed.
   A constant is stated only where the adapter knows everything the definition can
   change; otherwise it is listed with the reason, and a layer that needs it says so.

   **Rates.** The two times of a rate are two rows of the one time base the replay steps
   through: of the engine's two bases (`accepted`, the state's rows, and `observation`,
   the observed rows) the observed one where the run has it. A total saved on the other
   base only is read at the rows of that base that fall exactly on those times, and is
   not used where a time has no such row. **No rate is taken across a reset.** A total
   that says `resets` restarts at nought on a slot when one of the operators it names
   retires that slot: the retired slot's history moves into that operator's own record,
   so a difference across such an event is the operator's booking and no flow. The
   events of the layers those operators own say when it happens and at which cell. For
   an entity of that cell (the cell itself, its membranes and what lies on them, its
   junctions) the interval that holds such an event has no rate, and the page says so.
   An event at a record's own time counts for both intervals it bounds, and an entity
   that cannot be traced to a cell has no rate in any interval that holds such an event.
   A layer may take the rate of every one of several saved totals: each total the run
   saved is read by itself, and a total saved once for each species is read for every
   species. Rates are never added to one another: each element that has a total has its
   own sign.

   **A signed record is drawn with a direction only where its sign is declared.** There
   are two ways a run reaches the viewer, and the legend says which one stands behind a
   direction:
   - **Packaged from the engine's own view** (`view.json`, `schema/RUN_VIEW.md`). Each
     sign is carried as that view declares it, by the roles of the record's set, with who
     confirmed it; the legend says "declared by the run's own view". Under the engine's
     view the viewer infers no kind and no sign: a record with no declared kind gives no
     rate, one with no declared sign no direction, and the page gives the view's own
     reason (`unstated`). Two things stay the viewer's own under such a view, and the
     page says so of each: which species is the secreted one, where the view names none
     as such, and where the tiles of a small world lie, where the view gives no geometry.
   - **Packaged with the viewer's own table**, for a run of the tissue family that has
     no such view. The table's convention was confirmed on 15 November 2026, by the owner
     of the engine's core (a positive transfer leaves the cell for its outside, or the
     sender for the receiver; pump cycles are positive inwards) and by the engine's lead
     (an exchange route's total, `exchange_moved_fmol`, is positive out of the cell, for
     an export and an import route alike: the operator's own check holds an export's
     total at nought or more and an import's at nought or less). The legend says that the
     convention is the engine's own, confirmed and not declared in that run's files
     (`docs/ENGINE_NEEDS_FOR_QUANTITY_LAYERS.md`). An exchange route is drawn with that
     direction only where the run's own amounts agree with it: where they add up read
     that way, and under no other reading. Two readings go beyond what was confirmed, and
     each is named as the viewer's reading wherever it is used:
     - the sign of the membrane voltage, read from the run's files (the cell's potential
       less that of its outside);
     - that an operator's ledger which the table does not list (the ledgers of what was
       made and cleared of a secreted species) is a total since the start, read from its
       array where it begins at nought and never falls.
2. **One layer on each visual channel.** The channels are `colour`, `height`, `links`
   (signs on junctions), `surface` (signs on a membrane), `arrows`, `motion` and `glow`.
   Switching a layer on takes its channels from whichever layer held them. Layers on
   different channels show together.
3. **Something moves only where a rate stands behind it.** A level or a difference never
   moves. A bead is a token of a rate: the legend says how much one stands for. A layer
   on the `motion` channel states its time on the picture: true speed, how much it is
   slowed, or the loop it plays; and what one token stands for. The rate sets how many
   tokens pass, never how fast one travels. The interval the rate is a mean over stands
   with the time. An arrowhead ends each lane that carries something and points the way
   its tokens go, so that a still picture, and a visitor who asks for less motion, are
   told the way. Where nothing may move, the tokens stand, as many as would be on their
   way at one moment, and the picture says that it is shown still; a stream too thin for
   one token shows a small arrowhead alone.
4. **Always a legend:** the quantity, its unit and scale, what stands behind it (the
   record's owner and how it is represented), and for a derivation the rule and its
   inputs. Text wears the page's text colours, never the mark's colour. For a run
   packaged from the engine's own view, how a record's part of the engine is represented
   and who owns it are the view's own words for its layer.
5. **What a run did not save is said.** A layer whose record a run lacks is listed,
   switched off, with "this run did not save it".
6. **Examples are marked and kept apart.** Where no saved run carries a layer's record,
   the layer may be shown on an example run with invented numbers. Such a run is made by
   the run-fixture tool, stands under "Examples" and never among the experiments, has no
   result class, and carries "Example: invented numbers" on the picture and in the
   legend for as long as it is shown. The run folder says of itself that it is an example
   (`example.json`, which the run-fixture tool writes). The adapter carries that into the
   run's view, names no model as the owner of a record, and refuses to list the run under
   an entry that is not marked `example` (and a run that is none under one that is).
7. **Drawn where the run is shown; in the Cell view only from that cell's own run.** A
   layer fed by a run is drawn in that run's replay: on the sheet, or on a close-up of
   one chosen cell's membrane, named with the run, the cell, the membrane and the time,
   and with what its numbers are worked out from. In the Cell
   view of a species it is drawn only from that species' own looping run, a run the
   engine made of that one cell and packaged to loop. The picture then names the run,
   says that it loops, and gives the loop's length in the cell's time and how much it is
   slowed. A species with no such run shows no run-fed layer in its Cell view. A
   packaged replay says that it is such a loop in its view (`loop`,
   `schema/RUN_VIEW.md`): the species whose cell it is, the cell, and the run's own word
   that its last record meets its first. The viewer refuses a run that is an example,
   that names no model of the engine or no revision, that is another species' cell, or
   that does not say it closes. The loop is the run's records from the first to the
   closing one; every rate is a mean between two records that both lie inside it, and
   no difference is taken across the seam.
8. **Colour by the job it does:** one hue for a level, two hues about a neutral middle
   for a signed quantity, each validated for colour-blind readers against the light and
   the dark surface. Each ion has one fixed colour everywhere, with its name beside it:
   three ion colours that every reader can tell apart on both surfaces. Any other species
   wears one neutral tone, with its name beside it.
9. **Strength is a setting.** Each mark draws `quiet` or `bold`; the default is the one
   the user chooses from pictures of both.
10. **Size.** A layer's records may come in a file of their own beside the run's replay,
    fetched when the layer is switched on, so that a replay stays near 1 MB whatever
    layers its run can feed.
11. **Illustration in the Cell view is a class of its own, off when the page opens** (the
    user allowed it on 15 November 2026). Where a species has no looping run, flux may be
    shown in its Cell view only as illustration, in one of two declared forms: `typical
    values`, from a cited source and not from a run; or `direction only`, where the count
    of tokens stands for no number. It carries "Illustration: not a run" on the picture
    and in the legend for as long as it is shown, never shares a picture with a run-fed
    layer, and is not offered for a part the species' file says it lacks. In its form
    `direction only` every lane shows the same number of beads at the same pace, and the
    picture says that the number of beads and their pace stand for no number. The words
    "Illustration: not a run" stand in the panel of a chosen part as well, since a
    narrow screen hides the legend behind a panel. The form `typical values` is declared
    and holds no entries; it is not offered until an entry with a cited source stands
    behind each number.
12. **Decoration never moves with a direction.** Motion that is not a layer (a drifting
    crowd, a shimmering membrane) has no net direction, stops while any layer on the
    `motion` channel shows, and stops for a visitor who asks for reduced motion.

## Flux in the Cell view

The user's choices of 15 November 2026, from the page of options
(`docs/FLUX_AND_LOOK.md`): flux is drawn as **beads, with bloom**; it opens at **true
speed**, with what one bead stands for on the picture and a slow-down the visitor sets
beside it; at rest nothing flows, **a part's flux shows when the part is selected, and a
Flux switch shows all of it**; its numbers come first from the species' own looping run,
and **illustration is allowed** where there is none (rule 11); and **all of it flows**:
ions through channels and pumps, the exchange with neighbours, water, secreted signals
and fuel, each where a rate stands behind it.

**How it is switched.** The legend of the Cell view has a Flux switch, off as the page
opens. A part's flux shows when the visitor chooses the part, alone, whatever the
switch; the switch shows all of it. A part that the page's address names is chosen as
the page opens and shows no flux until the visitor chooses a part or presses the
switch: nothing flows as the page opens. A chosen part that draws nothing (see below)
shows nothing, and its reason. While any flux shows, the bloom is on, the look's own
motion is held still (rule 12), and the picture's own tokens of that part (the drops
where water crosses, the signals that leave, the ions in the close-up's channel) give
way to the beads. At rest those tokens stand still: they are the bodies of their parts
and do not move.

**One source at a time.** A species' cell shows flux from its own looping run (rule 7),
or, where it has none, as illustration (rule 11). A species with a run shows no
illustration, even for what its run lacks: that is named as not read from the run.

**Every direction drawn has a declared basis, and the page says which.** For a looping
run it is the run's own signs. For illustration it is a law of the engine, cited by its
id, the file it was read in and the revision (`data/layers/flux.json`, format
`cells.visualizer.flux@1`; the viewer keeps the words and does not read the engine, so
the file is brought up to date by hand when a law changes). A law of the engine speaks
for the engine's generic cell: it is drawn on a species only where the page shows that
species as the generic cell, or as modelled, and the species' file has no words of its
own on the part. Where no basis gives a direction, both ways are drawn side by side and
the page says that neither is claimed to carry more; or nothing is drawn and the reason
is given. No textbook direction is drawn.

| What flows | Drawn as illustration | Basis |
| --- | --- | --- |
| Ions through channels | both ways, none claimed | none: it depends on the voltage and the concentrations, which only a run knows |
| Ions through pumps | sodium out and potassium in; calcium out | `nak_atp_mass_action_positive@1` (3 out and 2 in for a forward cycle) and `ca_atp_mass_action_positive@1` (1 out); the lanes show as many beads as each other, and the three and the two stand in words. Not drawn for a species the law does not speak for |
| Exchange with neighbours | both ways, none claimed | none: it depends on both cells |
| Water | both ways, none claimed | none: it follows osmotic pressure |
| Secreted signals | released out, taken up in | `scheduled_species_exchange@1` (an export route carries out of the cell, an import route into it); both ways with none claimed where the law does not speak for the species |
| Fuel | nothing | no law of the engine says where fuel travels in the cell |

**Where a lane runs is the picture's choice,** and the legend says so: the engine has no
single channel or pump and no place for one. An illustration draws each lane at every
place the picture has for its part; a run gives each of its streams one lane, so that as
many beads pass as the run's rate says.

## Outside nodes on the picture

Where a run is a small world whose cells and outside nodes fit a lattice of tiles that
touch wherever a junction, a membrane or a face joins two of them, each outside node has
a tile. It is drawn flat, never as a cell, with its name on it; a bath held at a fixed
composition has a double edge and is called a held bath. The run saves no positions: the
layout is the viewer's, and the page says so. A layer on a border (`transfers`,
`energy-glow`) draws where two tiles meet.

## The first layers

| Layer | Idea | Lives on | Mark | Channel | Its numbers |
| --- | --- | --- | --- | --- | --- |
| `voltage-tint` | the colouring the replay has today | cell | `tint` | colour | record: membrane voltage |
| `voltage-relief` | 1 | cell | `relief` | height | record: membrane voltage |
| `junction-drops` | 2 | junction | `wedge` | links | the first a run can give of: the engine's own junction voltage; the `difference` of the two cells' potentials; the `difference` of membrane voltage where the run states that the cells' surroundings share one potential. With it, how far the junction's gate is open and whether a junction has formed |
| `ion-push-pull` | 3 | membrane of the chosen cell | `arrows` | arrows | `potential terms` for each ion, on the close-up of the chosen cell's membrane |
| `membrane-charge` | 4 | membrane of the chosen cell | `stipple` | surface | `charge`, counted on a piece of 100 nm by 25 nm |
| `transfers` | 5 | junction, face, membrane and exchange route: the border between the two places each joins | `stream` | motion | `rate` of every saved total carried (`junction_transferred`, `face_transferred`, `membrane_transferred`, `exchange_moved_fmol`), each species by itself |
| `ion-traffic` | 5 | the channel populations, the pump and the membrane itself, of the chosen cell | `beads` | motion | `rate` of `channel_transferred`; through the pump, the `rate` of its cycles times what one cycle moves of each ion, as the pump's declaration gives it; through the membrane itself, the `rate` of `membrane_transferred` |
| `energy-glow` | 6 | junction, face, membrane; a spot on the cell for its pump and for each channel population | `glow` | glow | `rate` of each `*_dissipated_energy_pJ` ledger by itself: a ledger that says `monotone`, or one that says `resets` |
| `signal-fog` | 7 | cell, and each outside node that has a tile | `fog` | colour | record: amount of the run's secreted species; on as such a run opens |

`voltage-tint` comes first and changes nothing a visitor sees: it proves the contract on
the colouring that exists, with the page's own checks as its guard.

`transfers` and `ion-traffic` both hold the motion channel: one of them shows at a time
(rule 2). `ion-traffic` draws, with no form, what crossed the membrane itself: the
engine's `membrane_transferred` holds the passive membrane routes only, and what each
channel population and each pump carried is its own ledger. The engine's run view notes
this of the field, and the engine's lead confirmed it on 15 November 2026: the three
ledgers stand side by side and count nothing twice
(`docs/ENGINE_NEEDS_FOR_QUANTITY_LAYERS.md`).

## How a layer names its numbers

- **Several sources, tried in order.** A layer may list its quantities under `first_of`:
  the first one the run can give is used, and the legend says which. A record may be
  named by several names, tried in order, so that the engine's own readout is taken
  before a name an older driver used.
- **What goes with it.** A layer may list records under `also`, each with a `role` the
  mark knows (`gate`: how far a junction is open; `formed`: whether a junction exists),
  what it `says`, and what the mark shows `without` it.
  Further roles: `outside` (the amount in each outside node); `made`, `cleared` and
  `cleared outside` (an operator's ledgers of the species, given as numbers); `pump` (a
  pump's cycles, or its ledger); `channels` (the channel populations' ledger).
- **Every one of several totals.** A `rate` may name its totals under `any_of`.
- **A rule with several inputs** names, for each part, what may fill it, in the order
  tried: a saved record, a field saved once for each species, a named constant of the
  definition, or `{amount, over}` (an amount over the volume of its compartment).
- **The secreted species.** A layer may ask for `species: secreted`: the species the
  run's view names as secreted (`sets.species.secreted`). A run that names none cannot
  feed it, and is told so.
- **On as a run opens.** A layer that says `opens` holds its channel as a run that can
  feed it opens; the sheet's height then stays flat.
- **A record no layer names** is still offered where a mark can show it plainly: a level
  on the cells as a colouring and a relief, under the record's own name and unit.
- **Strength, for the relief:** `quiet` is the height the sheet always had; `bold` stands
  the same values higher and adds a bar that says how many millivolts a step is, and a
  line where the sheet crosses a mark the experiment itself declares.
- **What stands behind a layer** (rule 4) is said in a panel opened from the layers'
  switch: the record, its owner and representation, and for a derivation the rule and
  its inputs.

The engine's standard history already holds what layers 5 to 7 need (amounts transferred
per channel, pump, junction and face; energy dissipated per element; amounts per cell and
per outside node). The engine's first development run for the viewer (15 November 2026:
one cell, its surroundings, a secreted species) feeds the fog, the transfers and the
glow. No saved run of a sheet carries the totals yet: ion traffic through channels and
pumps, and transfers and glow on a sheet, are shown on an example (rule 6) until one
does.
