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
   moves. A token (a packet or a bead) is a token of a rate: the legend says how much one
   stands for. A layer on the `motion` channel keeps the clock of what it is drawn in (the
   user, 16 November 2026, asked whether beads keep a clock of their own or follow the
   playhead: "the replays and you must be able to slow down and make replays faster"). On
   a replay that is the replay's own clock: its tokens stand while the replay is paused
   and, while it plays, as many pass as the rate gives over the stretch of the run the
   playhead covers. A replay may be slowed below true speed and made faster than it, from
   its timeline, which says in words what each step is. In the Cell view a looping run
   keeps its loop's clock, slowed from the legend's slider.

   **How a rate is drawn follows the speed the picture keeps, so that slowing down is
   seen** (the user, 17 November 2026: "the speed does not change the anymation of the
   beads and arrows in flux"; "nice visual effects to show the speed at full speed, you
   wont see any individual ions"). At true speed no single particle can be followed: each
   lane is a stream, as wide and as bright as its rate (the busiest the fullest), and the
   picture says the busiest's rate in numbers. Slowed, the stream resolves into packets
   and then into single beads, with no jump between: fewer pass a second and each crosses
   more slowly, the more the picture is slowed. A token stands for 1, 2 or 5 times a
   power of ten of what flows, never under one particle, and the tokens passing a second
   times what one stands for is the rate at the speed in force, exactly. The rate sets how
   many tokens pass and how wide a stream is, never how fast one travels: how fast a
   streak, a packet or a bead goes is a sign of the slow-down and stands for nothing
   measured.

   The picture states what is drawn and what one token stands for, the speed (true speed,
   how much it is slowed or made faster), that the replay is paused where it is, the loop
   it plays, and the interval the rate is a mean over. Where an interval passes too fast
   to be read at the speed in force, the picture gives its length ("means over each 20 ms
   between records") in place of its place. The way a lane flows is shown by chevrons
   along it, which stand where nothing may move, so that a still picture, and a visitor
   who asks for less motion, are told the way; a stream too thin for one token shows its
   chevrons alone. Where nothing may move, the tokens stand, as many as would be on their
   way at one moment, and the picture says that it is shown still. Faster than true speed
   the lanes are streams as at true speed, and the picture gives the rate at full width
   both in the run's seconds and in the seconds of watching. However short a lane and
   however busy, no token overlaps the next on it: a packet is drawn shorter, and a bead
   smaller, never fewer; where lanes lie side by side a chevron is drawn no wider than
   leaves room to the next. A chevron is one flat, see-through mark a little paler than
   its lane, without a glow, so that it is not taken for a particle.

   The same holds in the Cell view and in a replay's sheet and close-up, which draw
   through one renderer. An illustration (a species with no run) has no rate and no
   speed: it keeps beads at one pace, with chevrons for the way, and never draws a
   stream, so that it cannot look like a measured one.
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
   slowed. A species with no such run shows no run-fed layer in its Cell view. The run
   belongs to the species' cell type (`cell_type.loop`, `CELL_TYPES.md`). The page finds
   it in its catalogue of runs and says what the catalogue says it is (a development run
   of the engine, not judged); while it is on its way, or where the page cannot have it,
   nothing is drawn and the reason is given, and illustration does not stand in for it.
   The picture says, in the fewest words, which of the run's cells the Cell view's cell is
   and what drives it that is not drawn, and that it is no measurement of a living cell;
   the legend and the panel say which part takes a flux from which record, and what the
   run's closure leaves out. A
   packaged replay says that it is such a loop in its view (`loop`,
   `schema/RUN_VIEW.md`, in the shape the engine's writer gives it): the species whose
   cell it is, the cell, the loop's period, and the run's own word that its last record
   meets its first, with how closely and within which declared tolerance. The viewer
   refuses a run that is an example, that names no model of the engine or no revision,
   that is another species' cell, whose period is not its records' span, or that does
   not close within its tolerance. The loop is the run's records from the first to the
   closing one; every rate is a mean between two records that both lie inside it, and
   no difference is taken across the seam. Of a looping run the viewer reads what
   crossed the cell's channel populations, its pump and its membrane itself (the totals
   of `ion-traffic`), and its junctions and its exchange routes (the totals of
   `transfers`), each the way the run's declared sign gives; what it does not read
   (water) is named as not read, and fuel keeps its own reason.
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
    behind each number. Where the cards over the picture leave the statement no room (a
    phone with its legend open; a narrow window with a card, the legend and a panel), the
    picture carries none, and the legend or the panel in front carries the notice: the
    words are in sight wherever illustration shows.
12. **Decoration never moves with a direction.** Motion that is not a layer (a drifting
    crowd, a shimmering membrane) has no net direction, stops while any layer on the
    `motion` channel shows, and stops for a visitor who asks for reduced motion. One
    exception, the user's of 16 November 2026 ("bring motion back"): in the Cell view
    the cell's own tokens (the drops where water crosses, the signals that leave, the
    ions in the close-up's channel) move at rest as they did before, each its own way.
    Their motion is the picture's own and stands for no measured flow, and the page says
    so beside the Flux switch. They hold still where they stood while any flux shows,
    those of a part whose flux shows give way to its beads, and they stand for a visitor
    who asks for reduced motion.
13. **A machine's own motion is illustration from papers, and says so** (the user, 16
    November 2026: "motor, yes it should turn at real life speeds at flux ... except if we
    slow down the flux"; and of the blur: "sounds good on the blur but you can skipt the
    too fast to follow text").
    - **Its basis.** In a closer view of a machine (`schema/MACHINES.md`), a part turns only
      where the machine's file gives a saved sentence of a permissive paper for its way,
      with the side it is seen from, and a sentence, a declared derivation or a stated choice
      within the range the sentences give, for its rate. This is the one exception to "No
      textbook direction is drawn" in "Flux in the Cell view".
    - **It is the machine's flux.** It moves while the machine is the part shown (opened by
      the visitor: "Look closer", the machine's stop on the scale rail), or while the Flux
      switch shows all. It stands when the address opens the closer view (until the visitor
      chooses), on a page opened still, and for a visitor who asks for reduced motion.
    - **Its speed.** It turns at real-life speed, at the rate the file draws. Only the Cell
      view's flux slow-down slows it: it keeps that one speed, offered in the legend's Speed
      slider while it turns, and has no speed, no steps and no words for them of its own. Its
      clock is the real time that passed.
    - **An arrowhead shows the way** whenever the machine is drawn, turning or still.
    - **No mark may be read as another way or another rate.** The marks give way to a swept
      form, the marks smeared round into a body of revolution with no angle of its own:
      above an eighth of a turn in a frame for a single mark, and above a quarter of their
      spacing for a set of like copies, judging each frame by the larger of its own step and
      the smoothed step. The two fade into each other over the half step below the limit.
    - **What the picture states**, for as long as the machine shows (or the panel or sheet in
      front of it, where the picture has no room): "Illustration: not a run" while it turns;
      that Cells has no model of the machine; the way, and where it is seen from; and the
      speed: the rate drawn with what it rests on, and the top rate the papers give, or,
      slowed, the flux's own words for the slow-down with the rate in life. The panel names
      the papers. Nothing says that it is too fast to follow.
    - **It holds the motion channel**, so the look's own motion stops while it moves (rule
      12). It never shares a picture with a run-fed layer: the cell and its beads are
      faded out while the machine shows, and the picture's one statement is the machine's.
    - **Tokens through a part** follow rule 3. None is drawn yet: the user's decision of 16
      November 2026 was to wait with protons.
    - **A motion with no sentence** for its way or for its rate is not drawn. Where Cells
      comes to model the machine, its run's numbers take the place of the papers'.

## Flux in the Cell view

The user's choices of 15 November 2026, from the page of options
(`docs/FLUX_AND_LOOK.md`): flux is drawn as **beads, with bloom**; it opens at **true
speed**, with what one bead stands for on the picture and a slow-down the visitor sets
beside it; at rest nothing flows, **a part's flux shows when the part is selected, and a
Flux switch shows all of it**; its numbers come first from the species' own looping run,
and **illustration is allowed** where there is none (rule 11); and **all of it flows**:
ions through channels and pumps, the exchange with neighbours, water, secreted signals
and fuel, each where a rate stands behind it.

Since 17 November 2026 how a rate is drawn follows the speed (rule 3): a stream at true
speed, packets and then single beads as it is slowed. The Cell view's speed is a slider,
from true speed to ten million times slower, marked at a thousandfold (half way) and a
millionfold (three quarters); it never goes faster than life. The motor and a looping run
share it.

**How it is switched.** The legend of the Cell view has a Flux switch, off as the page
opens. A part's flux shows when the visitor chooses the part, alone, whatever the
switch; the switch shows all of it. A part that the page's address names is chosen as
the page opens and shows no flux until the visitor chooses a part or presses the
switch: nothing flows as the page opens. Once the switch has been pressed, the part the
address named shows as any chosen part does, and goes on showing when the switch is
turned off again. A chosen part that draws nothing (see below)
shows nothing, and its reason. While any flux shows, the bloom is on, the look's own
motion is held still (rule 12), and the picture's own tokens of that part (the drops
where water crosses, the signals that leave, the ions in the close-up's channel) give
way to the beads. At rest those tokens move, as rule 12's exception allows: they are the
bodies of their parts, and their motion is the picture's own.

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
is given. No textbook direction is drawn. A machine's closer view is not flux of the cell:
what moves there follows rule 13, the one exception.

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
many beads pass as the run's rate says. Drawn to scale, the membrane's close-up has lanes
of its own size through its channel and over its pump; its one pump carries the
sodium–potassium lanes.

**Colours.** A bead of sodium or of potassium wears that ion's colour; every other bead
wears the one neutral tone (rule 8). The picture's own hues for water and for signals
are not used for beads: only the ions' colours were validated together.

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
| `junction-coupling` | 2 | junction | `network` | links | each junction's own number as the run saves it: its conductance where it saves one, else its gate. A line between the middles of its two cells, across their border, as wide as the number (a gate's scale is nought to one, fully open; any other number's nought to a round number at or above its largest); a hairline, fainter, under a fiftieth of the scale. Transfers runs along the same line. A chosen cell's panel gives each of its junctions' number |
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
