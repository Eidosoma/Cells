// Flux in the Cell view (schema/QUANTITY_LAYERS.md, "Flux in the Cell view", with rules 3,
// 7, 11 and 12): what the cell lens holds to show what flows in the species' cell.
//
// At rest nothing flows. A part's flux shows when the part is chosen, alone; the Flux
// switch, off as the page opens, shows all of it. The mark is the bead layer's (beads with
// bloom, ./marks/tokens.js), on the cell picture's own geometry. While any of it shows,
// the look's own motion is held still (rule 12) and the bloom is on.
//
// At rest the cell's own drops, signals and close-up ions move (the user, 16 November
// 2026: "bring motion back"). That motion is the picture's own and no measured flow, and
// the legend says so beside the switch. While any flux shows they hold still where they
// stood, and those of the part whose flux shows give way to its beads (`flowing`, `takes`).
//
// Where the flux comes from is one of two declared classes, never both in one picture:
//   the species' own looping run (./loop.js, rule 7): true speed, with what one bead
//     stands for and a slow-down; the picture names the run, says what it is (a development
//     run of the engine, not judged, as its catalogue says), that it loops, the loop's length
//     in the cell's time, and what the cell drawn takes from it. The species names the run
//     in its file (`cell.loop`, a packaged replay's id); the page finds it in the replay
//     catalogue, fetches it and its records (want), and plays it. While it is on its way, or
//     where it cannot be had, nothing is drawn and the reason is given: a species that names
//     a run never falls back to illustration;
//   illustration (./flux.js, rule 11), where the species has no such run: it carries
//     "Illustration: not a run" on the picture, in the legend and in the chosen part's
//     panel for as long as it shows.
// Everything goes through the species' file: nothing is offered for a part the species
// marks absent, that the map leaves out, or that the cell drawn has no place for.
//
// Where a lane runs is the picture's choice: the engine has no single channel and no
// place for one. The legend says so.

import * as THREE from "../three.js";
import { readFlux, planFor, shownKinds, shownWithheld, illustrationWords, citation, PACE } from "./flux.js";
import { readLoop, loopAt, loopStreams, loopToken, loopRates, planFromLoop, loopWords, closesWords, engineWords, intervalWords, statusWords, takenWords, takenShort, everMoves } from "./loop.js";
import { Tokens } from "./marks/tokens.js";
import { fitOnRow } from "./statement.js";
import { SLOWS, SLIDER, SLOWEST, slowAt, positionOf, slowLabel, statementOf, tokenWords, timeWords, paceAt, paceKey, modeAt, resolveAt, flowWords, ionsASecond, CROSSING, STILL_WORDS, HEAD_WORDS } from "./marks/beads.js";
import { STYLES } from "./marks/flow.js";
import { ionColours } from "./ions.js";
import { clock } from "../replay/format.js";
import { speedWords } from "../replay/player.js";
import { loadRun, loadPart } from "../replay/source.js";
import { Catalogue } from "../replay/catalogue.js";
import declaredFlux from "../../data/layers/flux.json" with { type: "json" };
import ionTable from "../../data/layers/ions.json" with { type: "json" };

/** The id of the panel that says what stands behind the flux shown. */
export const FLUX_PANEL = "flux:all";
/** The id the legend's switch carries. */
export const FLUX_SWITCH = "flux";
/** How strongly the beads bloom (core/look.js: stage.setBloom). */
export const BLOOM = 0.6;
/** What the legend says, beside the switch, of the motion the cell's own tokens have at rest. */
export const REST_WORDS = "What moves at rest is the picture's own, not a measured flow.";
/** Under this width (a phone) a looping run's statement on the picture is its notice and its name alone. */
export const PHONE = 600;
/** How the way a lane flows is drawn: chevrons along it (the page's), or, to compare, a tapered trail or an arrowhead at its end (marks/flow.js, STYLES). */
export const DIRECTION = "chevrons";
/** The statement on the picture, in pixels: where its top may lie at the highest (under the top bar), the gap between its notice and its lines, and the room kept round it. */
export const STATEMENT = { top: 64, gap: 6, margin: 6 };

/**
 * The sizes of the mark in the cell's frame, for each size mode: a bead's radius, how far
 * apart two lanes at one place run, how far a lane reaches to each side of the membrane,
 * how far above the cut face each kind's lanes run (clear of the parts they pass), and how
 * far apart the two lanes of a junction run.
 */
export const SIZES = {
  // Schematic: a bead about as large as the picture's own drops, so that it can be seen with the whole cell in view.
  // Two lanes at a channel run over its two walls, a quarter of a unit to each side of its pore.
  schematic: { bead: 0.15, pitch: 0.46, reach: 1.15, over: { channels: 0.46, membrane: 0.46, pumps: 0.68, junctions: 0.46, water: 0.4, secretion: 0.2 }, bridge: 0.92 },
  real: { bead: 0.09, pitch: 0.27, reach: 0.7, over: { channels: 0.14, membrane: 0.14, pumps: 0.14, junctions: 0.14, water: 0.16, secretion: 0.1 }, bridge: 0.27 },
};

/**
 * The pump of the membrane's close-up, drawn to scale (lenses/cell_parts.js, buildMolecules):
 * it stands `beside` nanometres along the membrane from the close-up's channel, its lobes up
 * to about 5 nm above the cut. Its lanes run `over` nanometres above the cut, clear of the
 * lobes, from `reach` nanometres outside the membrane to as far inside, `pitch` apart.
 */
export const CLOSE_PUMP = { beside: 24, over: 5.5, reach: 11, pitch: 1.4 };

/**
 * Where the close-up's pump stands, in the cell's frame: the builder's own handle for it where
 * it gives one (`pumpAt`), else the place the builder stands it at, along the membrane from the
 * channel (`sideways` points the other way along it), raised to where its lanes run.
 */
export function closePump(molecule, sideways, nm) {
  const at = molecule.pumpAt ? molecule.pumpAt.clone() : molecule.centre.clone().addScaledVector(sideways, -CLOSE_PUMP.beside * nm);
  return at.setY(molecule.centre.y + CLOSE_PUMP.over * nm);
}

/**
 * Where a kind of flux has a place on the cell as drawn: its seats. `cell` are the
 * handles of the cell's builder (lenses/cell_parts.js): its frame with the outline at the
 * cut, the angles at which its parts stand (`spots`), the old water streams and the path
 * its signals leave by. A seat is { inward(lateral), outward?(lateral) }: `inward` gives
 * the lane's path from outside the cell to inside it, moved `lateral` along the membrane;
 * a seat with `outward` has a path of its own for what leaves.
 */
export function seatsOf(kind, cell, mode, { sides = 0 } = {}) {
  const size = SIZES[mode], spots = cell?.spots, outline = cell?.frame?.outline;
  if (!size || !spots || !outline) return [];
  const cut = cell.frame.cut, reach = size.reach;
  const across = (angle, from, to, y) => ({ inward: (lateral = 0) => (share) => outline.walk(angle, lateral, from + (to - from) * share, y) });
  if (kind === "channels") return spots.channels.map((angle) => across(angle, reach * 0.9, -reach * 1.1, cut + size.over.channels));
  if (kind === "membrane") return (spots.charges || []).map((angle) => across(angle, reach * 0.9, -reach * 1.1, cut + size.over.membrane));
  if (kind === "pumps") return spots.pumps.map((angle) => across(angle, reach * 0.9, -reach * 1.2, cut + size.over.pumps));
  // A junction joins the cell to its first neighbour: "into the cell" is from the neighbour, across the cleft.
  // A run's junctions each cross a side of their own where the cell faces `sides` neighbours: the sides face them at
  // equal turns from the first (lenses/cell_layout.js, SPOT). Which junction of the run takes which side is the picture's choice.
  if (kind === "junctions") {
    if (spots.junction === null || spots.junction === undefined) return [];
    const turns = sides > 1 ? sides : 1;
    return Array.from({ length: turns }, (_, k) => across(spots.junction + (k * 2 * Math.PI) / turns, (spots.gap || 0) + reach * 0.9, -reach * 0.9, cut + size.over.junctions));
  }
  if (kind === "water") {
    const far = cell.streams?.[0]?.reach ?? reach * 1.6;
    return cell.streams?.length ? spots.water.map((angle) => across(angle, far, -far * 0.9, cut + size.over.water)) : [];
  }
  if (kind === "secretion") {
    if (!cell.signals?.length) return [];
    // What leaves goes the way the picture's signals leave; what is taken up crosses beside that corner.
    const beside = across(spots.secretion, reach * 1.4, -reach * 0.9, cut + size.over.secretion);
    return [{ inward: (lateral = 0) => beside.inward(lateral - 2.4 * size.pitch), outward: () => (share) => cell.signalPath(share) }];
  }
  return [];
}

/**
 * The lanes of one kind laid on its seats: [{ lane, path, reverse }]. An illustration
 * draws each lane at every seat of its group, since its counts stand for no number; a run
 * gives each stream one lane, so that as many beads pass as the run's rate says: the
 * streams of one element of the run (one channel population, the pump, one junction) share
 * a seat, side by side, and the elements are dealt over the seats in turn. Lanes that share
 * a seat run side by side, `pitch` apart.
 */
export function arrange(kind, seats, { every, pitch }) {
  if (!seats.length) return [];
  const at = seats.map(() => []);
  const lanes = kind.groups.flatMap((group) => group.lanes);
  const elements = [];
  for (const lane of lanes) {
    const name = lane.stream?.name ?? lane.key;
    if (!elements.includes(name)) elements.push(name);
  }
  lanes.forEach((lane, index) => {
    const element = elements.indexOf(lane.stream?.name ?? lane.key);
    const places = every ? (lane.spots ? lane.spots.filter((spot) => spot < seats.length) : seats.map((_, spot) => spot)) : [(lane.stream ? element : index) % seats.length];
    for (const spot of places) at[spot].push(lane);
  });
  const placed = [];
  at.forEach((here, spot) => {
    here.forEach((lane, index) => {
      const seat = seats[spot], lateral = (index - (here.length - 1) / 2) * pitch;
      // A lane of a run turns with its total's sign: it is laid inward and reversed when what moved left the cell.
      const own = lane.way === "out" && seat.outward ? seat.outward(lateral) : null;
      placed.push({ lane, key: `${lane.key}@${spot}`, path: own || seat.inward(lateral), reverse: own ? false : lane.way === "out" });
    });
  });
  return placed;
}

const { flux: FLUX, problems: PROBLEMS } = readFlux(declaredFlux);
export { FLUX, PROBLEMS };

export class CellFlux {
  /** `lens` is the cell lens; `flux` the checked declarations (data/layers/flux.json as the page ships it, unless a test gives its own). */
  constructor(lens, flux = FLUX) {
    this.lens = lens;
    this.flux = flux;
    this.on = false; // the Flux switch: off as the page opens
    this.slow = 1; // a run opens at true speed, unless the page's address carries a slow-down (`slow=1000`)
    const asked = Number(new URLSearchParams(globalThis.location?.search || "").get("slow"));
    if (asked >= 1) this.slow = Math.min(SLOWEST, asked);
    this.loops = new Map(); // species id -> its looping run, read
    this.fetches = new Map(); // species id -> { state: "fetching" | "failed", why }: a run the species names, not yet read
    this.plan = { kinds: [], withheld: [] };
    this.source = { kind: "illustration", form: "direction only" };
    this.tokens = []; // [{ tokens, zone, dust }]
    this.signature = null;
    this.lit = [];
    this.bloomed = false;
    this.holding = false;
    this.last = null;
    this.elapsed = 0; // seconds of the cell's time the loop has played
    this.step = null;
    this.tags = null;
    this.said = null; // what the picture says of the flux it shows
    this.fitted = null; // where that statement has room on the screen, for the window and the cards as they were last seen
    this.taken = new Set(); // the parts whose flux shows now
    this.held = null; // the part the page's address chose: it shows no flux until the visitor chooses a part or presses the switch
  }

  // ------------------------------------------------------------ what the species has

  get species() {
    return this.lens.species;
  }

  get cell() {
    return this.lens.cells?.[this.lens.sizeMode] || null;
  }

  /**
   * The cell type shown (schema/CELL_TYPES.md): the lens's own where it has one, else the
   * species' default type from its entries (`cell_types`, `default_cell_type`), else the
   * species' own type as its file gives it (`cell_type`). Null for a species with none.
   */
  get cellType() {
    const species = this.species;
    if (!species) return null;
    return this.lens.cellType || species.cell_types?.find((type) => type.id === (species.default_cell_type ?? species.cell_types[0]?.id)) || species.cell_type || null;
  }

  /** What a looping run is kept under: the species and its cell type shown (a loop belongs to a cell type). */
  get typeKey() {
    return this.species?.id ? `${this.species.id}/${this.cellType?.id || "cell"}` : null;
  }

  /** The looping run of the cell type shown, as read, or null. */
  get loop() {
    return (this.typeKey && this.loops.get(this.typeKey)) || null;
  }

  /** The id of the looping run the cell type shown names (`cell_type.loop`), or null. */
  get named() {
    return this.cellType?.loop || null;
  }

  /** How many sides of the cell drawn face a neighbour: the cell's own sides where the species has a sheet. */
  get sides() {
    const shape = this.lens.levels?.cell?.shape;
    return shape?.kind === "prism" ? shape.sides || 6 : 6;
  }

  /**
   * Fetch the looping run the species names, and its records, from the page's replay
   * catalogue, and give it to the species (setLoop). Asked once for each species; what it
   * is doing, or why it could not, is kept for the legend and the panel.
   */
  want() {
    const species = this.species?.id, key = this.typeKey, id = this.named;
    if (!species || !id || this.loops.has(key) || this.fetches.has(key)) return;
    const catalogue = new Catalogue(this.lens.model?.raw?.replays);
    const entry = catalogue.byId.get(id);
    const fail = (why) => {
      this.fetches.set(key, { state: "failed", why });
      if (this.typeKey === key) {
        this.build();
        this.refresh(true);
        this.lens.onChrome?.();
      }
    };
    if (!entry) return fail(`The ${this.species.label}'s own run (${id}) is not among the runs this page carries.`);
    this.fetches.set(key, { state: "fetching", why: `The ${this.species.label}'s own run is being fetched.` });
    const experiment = catalogue.experimentOf(entry);
    const about = { title: experiment.label || null, status: statusWords(experiment), plain: experiment.plain || null, record: experiment.outcome?.text || null, catalogue: entry };
    (async () => {
      // A load the network gave up on (it was cancelled, or the connection failed) is asked for again, twice, a moment apart.
      const again = async (load) => {
        for (let attempt = 1; ; attempt++) {
          try {
            return await load();
          } catch (error) {
            if (attempt >= 3 || !(error instanceof TypeError)) throw error;
            await new Promise((resolve) => setTimeout(resolve, 1500 * attempt));
          }
        }
      };
      const run = await again(() => loadRun(entry));
      // The records the loop reads come in files of their own beside the run's: fetched first, so that the loop is read once.
      const first = readLoop(run, species);
      if (first.ok) for (const part of loopStreams(first.loop).needs) await again(() => loadPart(run, part));
      this.fetches.delete(key);
      const answer = this.setLoop(species, run, about, key);
      if (!answer.ok) throw new Error(answer.why);
      if (this.typeKey === key) this.lens.onChrome?.();
    })().catch((error) => fail(`The ${this.species?.label || "species"}'s own run could not be read: ${error.message}`));
  }

  /**
   * Whether the picture has a part for the species shown: the map has a capability for it,
   * the species does not mark it absent, the scene does not leave it out, and the cell as
   * drawn has a place for what would flow through it.
   */
  offers(part) {
    const { lens } = this;
    if (!lens.capabilityByPart.get(part) || !lens.draws(part)) return false;
    const kinds = (this.flux?.kinds || []).filter((kind) => kind.part === part);
    return kinds.some((kind) => (!kind.groups.length && !kind.stream) || seatsOf(kind.id, this.cell, lens.sizeMode).length > 0);
  }

  /**
   * Give a species its looping run (a packaged replay, opened, with its records fetched).
   * Returns { ok } or { ok: false, why }: a run that is refused changes nothing. `about` is
   * what the page's catalogue says of the run: its `title`, its `status` (a development run
   * of the engine, not judged), its `plain` words. The page calls this once the run the
   * species names has come (want); a test may call it with a run of its own.
   */
  setLoop(speciesId, run, about = {}, key = `${speciesId}/${(this.species?.id === speciesId && this.cellType?.id) || "cell"}`) {
    const read = readLoop(run, speciesId);
    if (!read.ok) return read;
    // From here on the species has a run, and illustration is no longer shown for it (rule 11), even where
    // nothing of the run can be read yet: everything is then withheld, with the reason. `needs` names the
    // files of records to fetch before calling this again.
    const streams = loopStreams(read.loop);
    const hasRoutes = [...run.sets.keys()].some((set) => run.sets.get(set)?.holds === "route" || set === "route");
    // A stream whose total never changes over the loop carried nothing: it gets no lane, and takes no seat from one that does.
    const moving = streams.streams.filter((stream) => everMoves(run, stream));
    this.loops.set(key, { ...read.loop, ...about, hasRoutes, streams: moving, busiest: streams.busiest, unread: streams.ok ? null : streams.why });
    this.build();
    this.refresh(true);
    return streams.ok ? { ok: true } : { ok: true, reads: false, why: streams.why, needs: streams.needs };
  }

  /** Work out what flows for the species and size mode shown. The lens calls this when it has built its cells. */
  build() {
    const loop = this.loop;
    const has = (part) => this.offers(part);
    if (!loop && this.named) this.want();
    const fetching = !loop && this.typeKey ? this.fetches.get(this.typeKey) : null;
    if (loop) {
      this.source = { kind: "run", loop };
      this.plan = planFromLoop(this.flux, loop, loop.streams, { has, unread: loop.unread });
      // A run with no exchange route has nothing secreted in it: that is not a total it failed to save.
      for (const item of this.plan.withheld) if (item.id === "secretion" && !loop.hasRoutes && !loop.unread) item.why = "The run has no exchange route: nothing is secreted or taken up in it.";
    } else if (fetching) {
      // The species names a run that is not read yet, or cannot be: nothing is drawn, illustration does not stand in, and the reason is given for each part.
      this.source = { kind: "pending", state: fetching.state, why: fetching.why };
      this.plan = { kinds: [], withheld: (this.flux?.kinds || []).filter((kind) => kind.only !== "run" && has(kind.part)).map((kind) => ({ id: kind.id, part: kind.part, label: kind.label, why: fetching.why })) };
    } else {
      this.source = { kind: "illustration", form: "direction only" };
      this.plan = this.flux ? planFor(this.flux, { species: this.species, has, capabilityOf: (part) => this.lens.capabilityByPart.get(part) || null }) : { kinds: [], withheld: [] };
    }
    this.builtFor = this.lens.sizeMode;
    this.signature = null;
  }

  /** Take down what is drawn: the lens is about to dispose of its zones. */
  clear() {
    for (const set of this.tokens) set.tokens.dispose();
    this.tokens = [];
    this.taken = new Set();
    this.signature = null;
    this.shine();
  }

  // ------------------------------------------------------------ what shows now

  /**
   * The part of the cell that the visitor chose, where a capability of the map is: its name
   * in the cell's builder, or null. A part that the page's address named is chosen as the
   * page opens, and is not the visitor's choice: nothing flows as the page opens.
   */
  chosenPart() {
    const { lens } = this;
    if (this.held && lens.selected === this.held) return null;
    const entity = lens.selected ? lens.model.get(lens.selected) : null;
    return entity?.kind === "capability" ? entity.part || null : null;
  }

  /**
   * The page's address named this part, and the page opened with it chosen: it shows no flux
   * until the visitor chooses a part (another, or this one again) or presses the switch.
   */
  hold(id) {
    this.held = id || null;
    this.refresh();
  }

  /** The visitor made a choice through the page (the viewer says so before it sets it): the address's choice holds nothing back any longer. */
  release() {
    this.held = null;
  }

  /** What shows now: { part, kinds, withheld }. */
  showing() {
    const state = { on: this.on, part: this.chosenPart() };
    return { part: state.part, kinds: shownKinds(this.plan, state), withheld: shownWithheld(this.plan, state) };
  }

  /** Whether the flux of a part shows now: the old tokens the picture drew there give way to the beads. (Asked in every frame: kept from the last refresh.) */
  takes(part) {
    return this.taken.has(part);
  }

  /** Whether any flux shows now: the picture's own tokens of the cell then hold still where they stood. */
  get flowing() {
    return this.tokens.length > 0;
  }

  /** Whether nothing may move: the visitor asks for less motion, or the picture is a still one. */
  still() {
    const { stage } = this.lens;
    return Boolean(stage.reducedMotion || stage.rig?.instant);
  }

  setOn(on) {
    if (this.on === Boolean(on)) return;
    this.on = Boolean(on);
    this.held = null; // the visitor pressed the switch: from here on a chosen part shows as any chosen part does
    this.refresh();
    this.lens.onChrome?.();
  }

  /**
   * The Cell view's one clock, as a speed: seconds of the cell's time for each second of
   * watching (1 is true speed; a slow-down of a thousand is a thousandth). The loop and a
   * machine's rotor keep it; it is the Experiments timeline's measure (replay/player.js), so
   * that a replay played in the Cell view later can take the same control. Today it is set
   * only through `setSlow`, and only to the slow-downs the Speed row offers (SLOWS).
   */
  get speed() {
    return 1 / this.slow;
  }

  /**
   * The slow-down in force, in the words the picture says it: "true speed", "slowed 1,000
   * times". The one place the Cell view's speed is put in words: a machine's closer view
   * (lenses/machine_view.js) says its own speed with these.
   */
  slowSaid() {
    return speedWords(1 / this.slow).phrase;
  }

  /**
   * Slow the Cell view's clock to any point from true speed to the slider's end (a number, or the slider's
   * `{ slow, live }`). What is drawn follows in place, without a new build, so that nothing jumps as the slider
   * moves; while it is dragged (`live`) the legend is left as it is, and it is written again when the slider is let go.
   */
  setSlow(value) {
    const live = typeof value === "object" && value !== null && value.live === true;
    const slow = Math.min(SLOWEST, Math.max(1, Number(typeof value === "object" && value !== null ? value.slow : value)));
    if (!(slow >= 1)) return;
    if (slow === this.slow) {
      if (!live) this.lens.onChrome?.();
      return;
    }
    this.slow = slow;
    this.retime();
    if (!live) this.lens.onChrome?.();
  }

  /** The clock's speed changed: each set of lanes takes its blend, its crossing and its fullest stream in place, and the rates and the words follow. */
  retime() {
    const run = this.source.kind === "run";
    if (!this.tokens.length || !run) return this.refresh(true);
    const crossing = paceAt(this.speed).crossing, full = (ionsASecond(this.loop.busiest) * this.speed) / loopToken(this.loop.busiest, this.slow);
    for (const set of this.tokens) set.tokens.setResolve(resolveAt(this.speed), { crossing, full });
    this.step = null;
    this.rates();
    this.words();
    this.lens.stage.invalidate?.();
  }

  /**
   * The colour of a lane, as CSS text: an ion's own where it has one (sodium, potassium),
   * else the one neutral tone (data/layers/ions.json, rule 8). Only those colours were
   * validated together, so no hue of the cell picture is put beside them: a bead of water
   * or of a signal is told by the part it passes, whose name stands beside it.
   */
  colourOf(lane) {
    const dark = Boolean(this.lens.stage.palette?.dark);
    return lane.species ? ionColours(ionTable, [lane.species], dark).get(lane.species) : ionTable.other[dark ? "dark" : "light"];
  }

  /**
   * Draw what shows now, or take it down. The lens calls this whenever its choice, its size
   * mode or its colours may have changed; nothing is rebuilt unless what shows has changed.
   */
  refresh(force = false) {
    const { lens } = this;
    // The address's choice lasts until the visitor chooses: another part, or none.
    if (this.held && lens.selected !== this.held) this.held = null;
    // The cell drawn in the other size mode may have other places for what flows.
    if (this.builtFor !== lens.sizeMode) this.build();
    const showing = this.showing();
    const palette = lens.stage.palette || {};
    // The speed is not in it: a slow-down is followed in place (retime), not by a new build.
    const signature = [this.species?.id, lens.sizeMode, this.source.kind, this.style || DIRECTION, palette.dark ? 1 : 0, palette.bg, ...showing.kinds.map((kind) => kind.id)].join("|");
    if (!force && signature === this.signature) {
      this.shine(); // the view may have been shown or left since
      return;
    }
    const changed = this.signature !== null && this.signature !== signature;
    this.signature = signature;
    for (const set of this.tokens) set.tokens.dispose();
    this.tokens = [];
    const zone = lens.zones.find((item) => item.name === "cell" && item.mode === lens.sizeMode);
    const size = SIZES[lens.sizeMode];
    if (zone && size && showing.kinds.length) {
      const run = this.source.kind === "run";
      const ground = new THREE.Color(palette.bg || "#ffffff");
      // A run's beads cross more slowly where it is slowed (a sign of the slow-down, marks/beads.js, paceAt); an illustration's at one pace.
      const crossing = run ? paceAt(this.speed).crossing : CROSSING;
      const laid = (item) => ({ key: item.key, lane: item.lane, path: item.path, reverse: item.reverse, colour: new THREE.Color(this.colourOf(item.lane)), perSecond: run ? 0 : PACE, crossing });
      // A run is drawn by its speed: a stream at true speed, packets, then beads (marks/beads.js, modeAt); a stream is as
      // wide as its rate beside the loop's busiest. An illustration's beads stand for no number, and stay beads.
      const resolve = run ? resolveAt(this.speed) : 6, style = STYLES.includes(this.style) ? this.style : DIRECTION;
      const full = run ? (ionsASecond(this.loop.busiest) * this.speed) / loopToken(this.loop.busiest, this.slow) : null;
      const draw = (lanes, radius, home, dust) => {
        if (!lanes.length) return;
        const tokens = new Tokens({ lanes, radius, ground, resolve, style, full });
        home.root.add(tokens.group);
        this.tokens.push({ tokens, zone: home, dust, lanes });
      };
      const lanes = [];
      for (const kind of showing.kinds) {
        lanes.push(...arrange(kind, seatsOf(kind.id, this.cell, lens.sizeMode, { sides: run ? this.sides : 0 }), { every: !run, pitch: kind.id === "junctions" ? (run ? size.pitch : size.bridge) : size.pitch }).map(laid));
      }
      // Drawn to scale, the cell's own lanes are far too large beside one channel: they fade with the
      // membrane's dots as the camera comes close, and lanes of the close-up's own size take their place there:
      // through its channel, and over the pump beside it.
      const real = lens.sizeMode === "real";
      draw(lanes, size.bead, zone, real);
      const molecule = this.cell?.molecule, close = lens.zones.find((item) => item.name === "molecules" && item.mode === lens.sizeMode);
      if (real && close && molecule) {
        const nm = 0.001 / this.cell.frame.u;
        const sideways = new THREE.Vector3().crossVectors(new THREE.Vector3(0, 1, 0), molecule.outward).normalize();
        const near = [];
        const through = showing.kinds.find((kind) => kind.id === "channels");
        if (through && molecule.pored) {
          const seat = { inward: (lateral = 0) => (share) => molecule.ionPath(share).addScaledVector(sideways, lateral) };
          near.push(...arrange(through, [seat], { every: !run, pitch: 0.7 * nm }).map(laid));
        }
        // The close-up has one pump: an illustration's sodium–potassium lanes stand there (the calcium pump's are on the cell's third pump).
        const pumping = showing.kinds.find((kind) => kind.id === "pumps");
        if (pumping) {
          const at = closePump(molecule, sideways, nm);
          const seat = { inward: (lateral = 0) => (share) => at.clone().addScaledVector(molecule.outward, (CLOSE_PUMP.reach - share * 2 * CLOSE_PUMP.reach) * nm).addScaledVector(sideways, lateral) };
          near.push(...arrange(pumping, [seat], { every: !run, pitch: CLOSE_PUMP.pitch * nm }).map(laid));
        }
        draw(near, 0.3 * nm, close, false);
      }
    }
    this.taken = new Set(this.tokens.length ? showing.kinds.map((kind) => kind.part) : []);
    this.step = null;
    this.last = null;
    if (this.source.kind === "run") this.rates();
    this.shine();
    this.words();
    this.advance(0);
    lens.stage.invalidate?.();
    if (changed) lens.onChrome?.();
  }

  /** A run's rates at the record the loop stands at: each lane's beads a second, and its way. */
  rates() {
    const loop = this.loop;
    if (!loop) return null;
    const at = loopAt(loop, this.elapsed);
    if (at.step === this.step) return at;
    this.step = at.step;
    const token = loopToken(loop.busiest, this.slow);
    const rates = loopRates(loop, loop.streams, at.step, token, this.slow);
    for (const set of this.tokens) {
      for (const item of set.lanes) {
        const rate = rates.find((entry) => entry.stream === item.lane.stream);
        set.tokens.setRate(item.key, rate?.perSecond || 0, rate?.out === true);
      }
    }
    this.words();
    return at;
  }

  /** What every stream of the loop carries over the interval shown, for the panel and the tests. */
  readings() {
    const loop = this.loop;
    if (!loop) return [];
    const at = loopAt(loop, this.elapsed), token = loopToken(loop.busiest, this.slow);
    return loopRates(loop, loop.streams, at.step, token, this.slow).map((rate) => ({ ...rate, interval: at.interval, token }));
  }

  // ------------------------------------------------------------ each frame

  /** The lens calls this once a frame while it is shown. Returns whether anything moves. */
  frame() {
    if (!this.tokens.length) {
      this.last = null;
      return false;
    }
    // Beads keep true time whatever the frame rate: the stretch is the time that passed on the clock.
    const now = performance.now();
    const seconds = this.last === null ? 0 : Math.max(0, (now - this.last) / 1000);
    this.last = now;
    return this.advance(seconds);
  }

  /** Advance by a stretch of watching time, in seconds. */
  advance(seconds) {
    const still = this.still();
    if (this.source.kind === "run" && !still && seconds > 0) {
      this.elapsed += seconds / this.slow;
      this.rates();
    }
    let moving = false;
    for (const set of this.tokens) {
      const fade = Math.max(0, set.zone.fade ?? 1) * (set.dust ? (this.lens.dustFade ?? 1) : 1);
      if (set.tokens.setFade(fade)) moving = set.tokens.tick(seconds, still) || moving;
    }
    this.pin();
    return moving;
  }

  /** Bloom and the hold on the look's own motion, for as long as flux shows in the lens shown; and no longer. */
  shine() {
    const { stage } = this.lens;
    // A machine's closer view hides the cell, and its beads with it: no bloom and no hold for what cannot be seen.
    const showing = Boolean(this.lens.active) && this.tokens.length > 0 && !this.lens.machine?.open;
    const lit = showing ? this.tokens.flatMap((set) => set.tokens.shines) : [];
    for (const object of this.lit) if (!lit.includes(object)) stage.glow?.(object, false);
    for (const object of lit) if (!this.lit.includes(object)) stage.glow?.(object, true);
    this.lit = lit;
    // The stage is shared with the other views: bloom is asked for only while flux shows here, and only the bloom asked for is switched off.
    if (lit.length && !this.bloomed) {
      stage.setBloom?.(BLOOM);
      this.bloomed = true;
    } else if (!lit.length && this.bloomed) {
      stage.setBloom?.(0);
      this.bloomed = false;
    }
    if (showing && !this.holding) stage.decoration?.pause("flux");
    if (!showing && this.holding) stage.decoration?.resume("flux");
    this.holding = showing;
  }

  // ------------------------------------------------------------ the words on the picture

  /**
   * What the picture itself says for as long as flux shows: for an illustration its notice
   * and its form; for a run its name, that it loops and the loop's length, then what one
   * bead stands for, the time and the interval the rates are means over. `ways` are the
   * same words broken in more and more places, the whole first: the first that has room
   * between the cards is the one shown.
   */
  statement() {
    // While a machine's closer view shows, the picture says what the machine's motion is (rule 13): one statement on the picture.
    const machine = this.lens.machine?.statement?.();
    if (machine) return machine;
    if (!this.tokens.length) return null;
    const still = this.still();
    if (this.source.kind === "illustration") {
      const [notice, form] = illustrationWords(this.flux, still);
      return { notice, ways: [form, form.replace(" and their pace ", "\nand their pace "), form.replace(": ", ":\n").replace(" and their pace ", " and their pace\n").replace(" · ", "\n")] };
    }
    const loop = this.loop, at = loopAt(loop, this.elapsed);
    const what = this.showing().kinds[0]?.token || "ion";
    // The interval: its place in the loop where it can be read at this speed, else its length (loop.js, intervalWords).
    const bead = statementOf({ token: loopToken(loop.busiest, this.slow), what, speed: 1 / this.slow, interval: at.interval, clock, still, flow: true, widest: ionsASecond(loop.busiest) }).replace(/ · (mean of .*|no rate at .*)$/, ` · ${intervalWords(loop, at.interval, this.slow)}`);
    // On a phone the picture keeps two lines: what the run is (the notice) and its name; the token, the speed and what the
    // cell takes from the run stand in the legend and the panel (the coordinator's ruling, 16 November 2026).
    const name = loopWords(loop, this.species.label, clock);
    if (this.lens.stage.width < PHONE) return { notice: loop.status, ways: [name.replace(/ · a loop of /, "\nloops every ").replace(/ of the cell's time$/, ""), name] };
    // What the cell takes from the run, in the fewest words; the legend and the panel say it in full.
    const lines = [name, bead, ...takenShort(loop)].join("\n");
    const narrow = lines.replace(/ · /g, "\n").replace(/, with a prescribed /, ",\nwith a prescribed ");
    // Where none of those has room between the cards (a short window), the phone's two lines: the notice and the run's name.
    const fewest = name.replace(/ · a loop of /, "\nloops every ").replace(/ of the cell's time$/, "");
    return { notice: loop.status, ways: [lines, lines.replace(/ · /g, "\n"), narrow, fewest] };
  }

  /** The lens has made its labels anew: the flux's own are made with them. */
  label(labels) {
    const anchor = () => new THREE.Vector3();
    this.tags = {
      labels,
      notice: labels.add({ text: "", anchor: anchor(), priority: 990, kind: "note label-region label-example", lift: 0 }),
      lines: labels.add({ text: "", anchor: anchor(), priority: 989, kind: "note label-region label-flow", lift: 0 }),
    };
    // What the picture says of its flux gives way to no other label: it stays for as long as the flux shows.
    this.tags.notice.boost = this.tags.lines.boost = 1000;
    this.said = null; // new labels: the words are written into them whatever they were
    this.words();
  }

  /** Write the picture's statement into its labels, or hide them. Nothing is laid out again where the words are the same. */
  words() {
    const tags = this.tags;
    if (!tags) return;
    const said = this.statement();
    if (said && this.said && said.notice === this.said.notice && said.ways.join("\u0000") === this.said.ways.join("\u0000")) return;
    this.said = said;
    tags.labels.setText(tags.notice, this.said?.notice || "");
    tags.labels.setText(tags.lines, this.said ? this.said.ways[0] : "");
    this.fitted = null; // other words need their room found again
    this.pin();
  }

  /**
   * Keep the statement at one place on the screen wherever the camera looks: it stays on the
   * picture for as long as flux shows. A label follows a point of the scene and stands just
   * above it, so the point is moved to where the label's foot is to lie on the screen. Where
   * the cards leave it no room at all (a narrow screen with its legend open over the
   * picture), it is not put under them in pieces: the legend in front then carries the notice.
   */
  pin() {
    const tags = this.tags, { stage } = this.lens;
    if (!tags) return;
    const said = this.said, camera = stage.camera;
    if (!said || !camera?.isCamera || !(stage.height > 0) || !(stage.width > 0)) {
      tags.notice.hidden = !said?.notice;
      tags.lines.hidden = !said;
      return;
    }
    // The room is found again whenever the window or a card over the picture has changed.
    const blocked = tags.labels.blocked?.() || [];
    const key = JSON.stringify([stage.width, stage.height, blocked.map((rect) => [Math.round(rect.left), Math.round(rect.top), Math.round(rect.right), Math.round(rect.bottom)])]);
    if (!this.fitted || this.fitted.key !== key) this.fitted = { key, place: this.fit(blocked) };
    const place = this.fitted.place;
    tags.notice.hidden = !said.notice || !place;
    tags.lines.hidden = !place;
    if (!place) return;
    camera.updateMatrixWorld(); // the camera may have moved in this frame, and its matrices are brought up to date only when the frame is drawn
    const across = (2 * place.middle) / stage.width - 1, down = (pixels) => 1 - (2 * pixels) / stage.height;
    const notice = said.notice ? (tags.notice.height || 18) + STATEMENT.gap : 0;
    tags.notice.anchor.set(across, down(place.top + (tags.notice.height || 18)), 0).unproject(camera);
    tags.lines.anchor.set(across, down(place.top + notice + (tags.lines.height || 18)), 0).unproject(camera);
  }

  /**
   * Where the statement has room, and in how many lines: { top, middle } in pixels of the
   * window, or null where there is none. It stands as high under the top bar as it can,
   * between the cards that lie over the picture (the view's card, the scale rail, a panel,
   * the legend) and as near to the middle of the window as they allow; on each row it is
   * said in the fewest lines that fit there. Never in the lower part of the picture, where
   * the foot is.
   */
  fit(blocked) {
    const tags = this.tags, said = this.said, { width, height } = this.lens.stage;
    const notice = said.notice ? (tags.notice.height || 18) + STATEMENT.gap : 0;
    // Each way of breaking the lines, measured once by the label layer.
    const ways = said.ways.map((text) => {
      tags.labels.setText(tags.lines, text);
      return { text, wide: Math.max(said.notice ? tags.notice.width || 0 : 0, tags.lines.width || 0), tall: notice + (tags.lines.height || 18) };
    });
    for (let top = STATEMENT.top; top <= height * 0.6; top += 8) {
      for (const way of ways) {
        if (top + way.tall > height * 0.6) continue;
        const middle = fitOnRow({ width, blocked, top, tall: way.tall, wide: way.wide, wanted: width / 2, margin: STATEMENT.margin });
        if (middle === null) continue;
        tags.labels.setText(tags.lines, way.text);
        return { top, middle };
      }
    }
    tags.labels.setText(tags.lines, ways[0].text);
    return null;
  }

  // ------------------------------------------------------------ the legend and the panel

  /** The switch, the notice and the signs, for the legend (ui/legend.js, `layers`); null where nothing of the species could flow. */
  legend() {
    const { plan, flux } = this;
    // A machine's closer view: the legend speaks of what moves there, and offers the Speed row while it turns.
    const machine = this.lens.machine?.legend?.();
    if (machine) return this.machineLegend(machine);
    if (!flux || (!plan.kinds.length && !plan.withheld.length)) return null;
    const showing = this.showing(), flowing = this.tokens.length > 0, still = this.still();
    const run = this.source.kind === "run";
    const groups = showing.kinds.flatMap((kind) => kind.groups);
    const keys = [];
    if (flowing) {
      const named = new Map();
      for (const lane of groups.flatMap((group) => group.lanes)) if (lane.species && !named.has(lane.species)) named.set(lane.species, this.colourOf(lane));
      if (named.size) keys.push({ key: "ions", chips: [...named].map(([label, colour]) => ({ label, colour })), text: "" });
      // What has no colour of its own wears one neutral tone, and is told by the part it passes.
      const neutral = ionTable.other[this.lens.stage.palette?.dark ? "dark" : "light"];
      if (groups.some((group) => group.lanes.some((lane) => this.colourOf(lane) === neutral))) keys.push({ key: "bead", text: "Sodium and potassium wear their own colours. Every other bead wears one neutral tone and is told by the part it passes" });
      if (run) {
        const loop = this.loop, what = showing.kinds[0]?.token || "ion";
        // What is drawn follows the speed: a stream as wide as its rate at true speed; packets, then beads, slowed.
        const said = flowWords({ speed: this.speed, token: loopToken(loop.busiest, this.slow), what, widest: ionsASecond(loop.busiest) });
        keys.push({ key: "bead", text: modeAt(this.speed) === "stream" ? `${said}. A stream's width and brightness carry its rate; how fast its streaks run stands for nothing` : `${said}. More of them a second means more ${what}s a second; how fast one travels stands for nothing. Where a lane passes less than one now and then, its chevrons alone show` });
        keys.push({ key: "time", text: `${timeWords(1 / this.slow)}. The run loops: ${clock(loop.length)} of the cell's time, then again from its start. ${paceKey(this.speed)}${still ? `. ${STILL_WORDS}` : ""}` });
        keys.push({ key: "way", text: "A lane flows the way its total grew over the interval shown, by the run's own signs" });
        keys.push({ key: "head", text: (this.style || DIRECTION) === "chevrons" ? "Chevrons along each lane point the way it flows; they stand where they are when nothing may move" : (this.style || DIRECTION) === "taper" ? "Each lane widens toward the end it flows to: its head leads the flow" : HEAD_WORDS });
        // What the cell drawn takes from the run, and how closely the run closes, in the run's own measure.
        keys.push({ key: "from", text: `${takenWords(loop)}. ${this.fromWords()}` });
        keys.push({ key: "closes", text: closesWords(loop) });
      } else {
        keys.push({ key: "bead", text: flux.illustration.forms["direction only"].says });
        if (groups.some((group) => group.claimed)) keys.push({ key: "way", text: "A lane that goes one way goes as a law of the engine declares for that part; the panel names the law" });
        if (groups.some((group) => !group.claimed)) keys.push({ key: "way", text: "Two lanes side by side, one each way: no direction is claimed. Which way more goes depends on the cell's state, which only a run knows" });
        keys.push({ key: "head", text: "An arrowhead ends each lane and points the way its beads go" });
        if (still) keys.push({ key: "time", text: STILL_WORDS });
      }
      keys.push({ key: "pump", text: "Where a lane runs is the picture's choice: the engine has no place for a single channel or pump" });
    }
    // The Cell view has no timeline: a looping run is slowed from the legend, in the same words as a replay's speed.
    const time = run && flowing ? this.speedRow() : null;
    const cannot = showing.withheld.map((item) => ({ id: item.id, label: item.label, why: item.why }));
    // A part is chosen (by the visitor) and draws nothing: the legend says so, in place of asking for a choice.
    const selected = this.lens.selected, part = selected && (this.lens.model.get(selected)?.kind === "capability" || this.lens.sceneryItem?.(selected));
    const chosen = Boolean(part) && !(this.held && selected === this.held);
    const nothing = chosen && !showing.kinds.some((kind) => kind.part === showing.part);
    // Where the legend lists what is not drawn and why, that says it; else the chosen part's panel does (inPanel).
    const ask = this.source.kind === "pending" ? this.source.why : cannot.length ? null : nothing ? "This part draws no flux: its panel says why." : "Or choose a part to see its flux.";
    return {
      title: "Flux",
      // An illustration says so for as long as it shows (rule 11); a run says what it is, as its catalogue does.
      example: flowing ? (run ? this.loop.status || null : flux.illustration.notice) : null,
      rows: [{ channel: "motion", label: "Show", options: [{ label: "Off", off: FLUX_SWITCH, on: !this.on }, { id: FLUX_SWITCH, label: "All", on: this.on, title: "Show all that flows in this cell" }] }],
      time,
      // While nothing flows the cell's own drops, signals and ions move (a chosen part that draws nothing included): the
      // picture's own motion, which the page says is no measured flow, wherever motion is allowed.
      hint: flowing ? null : [ask, still ? null : REST_WORDS].filter(Boolean).join(" ") || null,
      keys,
      cannot,
      // The view's card stands just above the legend: the signs, what is not drawn and the door to the panel keep to one line.
      compact: flowing ? "What the beads mean" : "Why nothing is drawn here",
      // With the switch on and no part chosen, a panel says what stands behind all of it; a chosen part's own panel says it of that part.
      details: flowing && !showing.kinds.some((kind) => kind.part === showing.part) ? FLUX_PANEL : null,
    };
  }

  /**
   * The Speed row: true speed, or slowed. Offered wherever a rate stands behind what moves: a
   * looping run as it flows, and a machine's rotor as it turns. A later step gives the whole
   * Cell view the Experiments timeline's control in its place.
   */
  speedRow(beads = true) {
    // A slider (ui/legend.js): true speed at its start, its marks at a half and three quarters, never faster than life. Its value is
    // said in words (what a second here is in the run and, where beads move, what the eye sees), for the eye and for a screen reader.
    const words = (position) => {
      const slow = slowAt(position);
      return beads && slow > 1.05 ? `${timeWords(1 / slow)}. ${paceKey(1 / slow)}` : timeWords(1 / slow);
    };
    return {
      kind: "slider",
      label: "Speed",
      value: positionOf(this.slow),
      marks: SLIDER.map((mark) => ({ at: mark.at, label: mark.label })),
      slowAt,
      short: (position) => slowLabel(slowAt(position)),
      words,
      options: SLOWS.map((value) => ({ id: value, label: slowLabel(value), title: words(positionOf(value)), on: Math.abs(this.slow - value) < 1e-9 })),
    };
  }

  /** The legend in a machine's closer view: the switch, the Speed row while the rotor turns, and what its motion means. */
  machineLegend(machine) {
    return {
      title: "Flux",
      example: machine.example,
      rows: [{ channel: "motion", label: "Show", options: [{ label: "Off", off: FLUX_SWITCH, on: !this.on }, { id: FLUX_SWITCH, label: "All", on: this.on, title: "Show all that moves" }] }],
      time: machine.turning ? this.speedRow(false) : null,
      hint: machine.hint,
      keys: machine.keys,
      cannot: [],
      compact: "What its motion means",
      details: null,
    };
  }

  /**
   * Which parts of the cell drawn take a flux from which of the run's records, in one line:
   * "channels from channel_transferred (kir_3, nav_3); pumps from pump_cycles (pump of
   * membrane_3)". Only for a run.
   */
  fromWords() {
    const parts = this.takenFrom().map((item) => `${item.label.replace(/^Ions through the /, "").replace(/^Exchange with /, "").toLowerCase()} from ${item.records.join(" and ")} (${item.elements.length > 3 ? `${item.elements.length} ${item.plural}` : item.elements.join(", ")})`);
    return parts.length ? `Drawn: ${parts.join("; ")}` : "Nothing of the run is drawn here";
  }

  /** For a run: each kind drawn, with the records its lanes are read from and the elements of the run they cross. */
  takenFrom() {
    if (this.source.kind !== "run") return [];
    return this.plan.kinds.map((kind) => {
      const streams = kind.groups.flatMap((group) => group.lanes.map((lane) => lane.stream)).filter(Boolean);
      return { id: kind.id, label: kind.label, records: [...new Set(streams.map((stream) => stream.source?.field || stream.record.id.replace(/\.[^.]+$/, "")))], elements: [...new Set(streams.map((stream) => stream.name))], plural: { junctions: "junctions", channels: "channel populations" }[kind.id] || "elements" };
    });
  }

  /** The lines of one group of lanes, for a panel. */
  item(kind, group) {
    const lanes = group.lanes.map((lane) => lane.label);
    return { label: kind.groups.length > 1 || group.label !== kind.label ? `${kind.label}: ${group.label}` : kind.label, detail: [...new Set(lanes)].join("; "), lines: [group.says, group.basis].filter(Boolean) };
  }

  /** Whether an id is the flux's own panel. */
  has(id) {
    return id === FLUX_PANEL && (this.plan.kinds.length > 0 || this.plan.withheld.length > 0);
  }

  /** The panel that says what stands behind all the flux of the species shown. */
  describe(id) {
    if (!this.has(id)) return null;
    const { flux, plan, species } = this;
    const run = this.source.kind === "run";
    const drawn = plan.kinds.flatMap((kind) => kind.groups.map((group) => this.item(kind, group)));
    const laws = [...new Set(plan.kinds.flatMap((kind) => kind.groups.map((group) => group.law)).filter(Boolean))];
    const forms = flux.illustration.forms;
    const name = species?.label || "This cell";
    if (this.source.kind === "pending") {
      return { id, kind: "flux", group: "biology", label: "What flows in this cell", eyebrow: "Flux", chips: [], plain: `${this.source.why} Nothing is drawn until it is read, and no illustration stands in for it.`, sections: [{ title: "Not drawn", items: plan.withheld.map((item) => ({ label: item.label, lines: [item.why] })) }] };
    }
    const loop = this.loop;
    return {
      id,
      kind: "flux",
      group: "biology",
      label: "What flows in this cell",
      eyebrow: "Flux",
      chips: run ? [{ label: loop.status || "From the looping run", title: "The species' own run, made by the engine and packaged to loop, as the page's catalogue of runs says it is" }] : [{ label: flux.illustration.notice, title: "Nothing here is a number from a run" }],
      plain: run
        ? `${loopWords(loop, name, clock)}. ${loop.plain ? `${loop.plain} ` : ""}${loop.record ? `The record: ${loop.record} ` : ""}${loop.closes.says.replace(/^./, (first) => first.toUpperCase()).replace(/\.?$/, ".")} ${closesWords(loop)}. ${engineWords(loop)}.${loop.follows.length ? " Where the loop follows a daughter cell, the beads are still read for its first cell: the hand-over is not drawn yet." : ""}`
        : `${flux.illustration.notice}. ${name} has no looping run of its own cell, so what flows is shown as illustration. ${forms["direction only"].says}.`,
      note: run ? "Every rate is a mean between two records that both lie inside the loop: no difference is taken across the seam." : flux.illustration.speaks_for,
      sections: [
        ...(run
          ? [{
              title: "What this cell takes from the run",
              note: `${takenWords(loop)}.${loop.label ? ` The run's own words for itself: “${loop.label}”.` : ""}`,
              items: this.takenFrom().map((item) => ({ label: item.label, detail: `from ${item.records.join(" and ")}`, lines: [`Through ${item.elements.join(", ")}, each in a lane of its own.`] })),
            }]
          : []),
        { title: "Drawn", note: "Where a lane runs is the picture's choice: the engine has no place for a single channel or pump.", items: drawn },
        { title: "Not drawn", items: plan.withheld.map((item) => ({ label: item.label, lines: [item.why] })) },
        ...(run
          ? [{ title: "Over the interval shown", items: this.readings().map((rate) => ({ label: [rate.stream.name, rate.stream.species].filter(Boolean).join(" · "), detail: rate.ions === null ? "no rate" : `${Math.round(rate.ions).toLocaleString("en-US")} a second ${rate.out === null ? "" : rate.out ? "out of the cell" : "into the cell"}`.trim(), lines: [`${rate.perSecond.toFixed(2)} beads a second, one bead being ${rate.token.toLocaleString("en-US")}; each crosses in ${Number(paceAt(this.speed).crossing.toPrecision(2))} s`] })) }]
          : [
              { title: "The laws the directions are drawn from", note: flux.engine.says, items: laws.map((law) => ({ label: law.id, detail: `${law.path} at ${flux.engine.branch} ${flux.engine.revision}`, lines: [`It declares ${law.declares}.`, law.limit].filter(Boolean) })) },
              { title: "The two forms of illustration", items: [{ label: "Direction only", lines: [`${forms["direction only"].says}.`] }, { label: "Typical values", lines: [`${forms["typical values"].says}. ${forms["typical values"].needs}`] }] },
            ]),
      ].filter((section) => section.items.length),
    };
  }

  /**
   * A part of the map as the panel shows it while its flux may show: with a section that
   * says what is drawn for it and on what basis, and what is not drawn and why. The notice
   * of an illustration stands in the section's title, so that it is in the panel too, where
   * a narrow screen hides the legend behind it.
   */
  inPanel(entity) {
    if (!entity || entity.kind !== "capability" || !entity.part) return entity;
    const kinds = this.plan.kinds.filter((kind) => kind.part === entity.part);
    const withheld = this.plan.withheld.filter((item) => item.part === entity.part);
    if (!kinds.length && !withheld.length) {
      // A part through which the picture draws no flux at all: its panel says so, and what the picture draws flux for.
      const drawn = [...new Set((this.flux?.kinds || []).filter((kind) => kind.groups?.length).map((kind) => kind.label).filter(Boolean))];
      // Only a part the species has and that no kind of flux names: one the species lacks, or one a kind names, gets no word here, as before.
      if (!this.flux || !drawn.length || this.lens.absent?.has(entity.id) || this.flux.kinds.some((kind) => kind.part === entity.part)) return entity;
      const list = drawn.map((label) => `${label[0].toLowerCase()}${label.slice(1)}`).join(", ").replace(/, (?=[^,]*$)/, " and ");
      return { ...entity, sections: [...(entity.sections || []), { title: "Flux", items: [{ label: "None drawn for this part", lines: [`The picture draws flux only for ${list}. This part is none of them.`] }] }] };
    }
    const run = this.source.kind === "run", pending = this.source.kind === "pending";
    const items = [...kinds.flatMap((kind) => kind.groups.map((group) => this.item(kind, group))), ...withheld.map((item) => ({ label: `${item.label}: not drawn`, lines: [item.why] }))];
    // A run says what it is in the panel too, since a narrow screen hides the legend behind it.
    const title = run ? `Flux, from the looping run${this.loop.status ? `. ${this.loop.status}` : ""}` : pending ? "Flux" : `Flux. ${this.flux.illustration.notice}`;
    const note = run ? `${loopWords(this.loop, this.species.label, clock)}. ${takenWords(this.loop)}.` : pending ? this.source.why : kinds.length ? `${this.flux.illustration.forms["direction only"].says}.` : null;
    return { ...entity, sections: [...(entity.sections || []), { title, note, items }] };
  }

  dispose() {
    this.clear();
  }
}

/** Where a law was read, for a test or a tool that lists the declarations. */
export const cited = (law) => (FLUX ? citation(FLUX, law) : null);
