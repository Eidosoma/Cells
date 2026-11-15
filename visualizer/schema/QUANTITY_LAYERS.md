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
  `channel population`, `pump population`, `face`, `outside node`, `world`); its `unit`;
  its `kind` (`level`, `amount`, `cumulative`, `rate`); for a signed record its `sign`
  (what positive means: from what, to what); its `owner` (the model, operator or law that
  computed it, as the run's definition names it); how its layer of the engine is
  represented (`simulated`, `modelled`, `prescribed`); and its times.
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
  has: `tint`, `relief`, `wedge`, `arrows`, `stipple`, `beads`, `glow`, `fog`. It says
  which visual channels it takes, builds itself for a run, moves to a time, makes its
  legend, and takes itself down.

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
     divided by the time between: a mean over that interval, and said to be one;
   - `charge`: capacitance times voltage, with the capacitance and the area as the run's
     definition gives them;
   - `potential terms`: for one ion at one membrane, the two terms of the engine's own
     electrochemical potential difference, R T ln(c inside / c outside) and z F V, and
     their sum, from the saved concentrations and voltage and the definition's
     temperature and valence (the engine's `electrochemical_potential`, in
     `src/cells/processes/electrochemistry.py`). Shown in millivolts, each divided by z F.

   A derivation reads its inputs as the run had them. A value that an operator of the
   run may change (a volume, a capacitance or an area, the composition of a held bath) is
   read from the definition only where no operator of that run changes it; otherwise the
   run must have saved it over time, or the layer is listed as one the run cannot feed.
   **A signed record is drawn with a direction only where its sign is declared.** Until
   the run view declares which way is positive, a layer shows the size alone; where a
   direction must be shown it is the viewer's reading of the engine's code, and the
   legend says so.
2. **One layer on each visual channel.** The channels are `colour`, `height`, `links`
   (signs on junctions), `surface` (signs on a membrane), `arrows`, `motion` and `glow`.
   Switching a layer on takes its channels from whichever layer held them. Layers on
   different channels show together.
3. **Something moves only where a rate stands behind it.** A level or a difference never
   moves. A bead is a token of a rate: the legend says how much one stands for.
4. **Always a legend:** the quantity, its unit and scale, what stands behind it (the
   record's owner and how it is represented), and for a derivation the rule and its
   inputs. Text wears the page's text colours, never the mark's colour.
5. **What a run did not save is said.** A layer whose record a run lacks is listed,
   switched off, with "this run did not save it".
6. **Examples are marked and kept apart.** Where no saved run carries a layer's record,
   the layer may be shown on an example run with invented numbers. Such a run is made by
   the run-fixture tool, stands under "Examples" and never among the experiments, has no
   result class, and carries "Example: invented numbers" on the picture and in the
   legend for as long as it is shown.
7. **Drawn where the run is shown.** A layer fed by a run is drawn in that run's replay:
   on the sheet, or on a close-up of one chosen cell's membrane, named with the run, the
   cell and the time. It is not drawn on a species' cell in the Cell view, which is not a
   run.
8. **Colour by the job it does:** one hue for a level, two hues about a neutral middle
   for a signed quantity, each validated for colour-blind readers against the light and
   the dark surface. Each ion has one fixed colour everywhere, with its name beside it.
9. **Strength is a setting.** Each mark draws `quiet` or `bold`; the default is the one
   the user chooses from pictures of both.
10. **Size.** A layer's records may come in a file of their own beside the run's replay,
    fetched when the layer is switched on, so that a replay stays near 1 MB whatever
    layers its run can feed.

## The first layers

| Layer | Idea | Lives on | Mark | Channel | Its numbers |
| --- | --- | --- | --- | --- | --- |
| `voltage-tint` | the colouring the replay has today | cell | `tint` | colour | record: membrane voltage |
| `voltage-relief` | 1 | cell | `relief` | height | record: membrane voltage |
| `junction-drops` | 2 | junction | `wedge` | links | `difference` of membrane voltage, with the junction's open fraction |
| `ion-push-pull` | 3 | membrane of the chosen cell | `arrows` | arrows | `potential terms` for each ion |
| `membrane-charge` | 4 | membrane of the chosen cell | `stipple` | surface | `charge` |
| `ion-traffic` | 5 | channel and pump populations of the chosen cell | `beads` | motion | `rate` of the amounts transferred |
| `energy-glow` | 6 | junction, membrane, pump | `glow` | glow | `rate` of the energy dissipated |
| `signal-fog` | 7 | cell and outside node | `fog` | colour | record: amount of a secreted species |

`voltage-tint` comes first and changes nothing a visitor sees: it proves the contract on
the colouring that exists, with the page's own checks as its guard.

The engine's standard history already holds what layers 5 to 7 need (amounts transferred
per channel, pump, junction and face; energy dissipated per element; amounts per cell and
per outside node). The runs kept on disk for the viewer did not keep it, so those three
start on examples (rule 6) and move to saved runs as soon as one carries the records.
