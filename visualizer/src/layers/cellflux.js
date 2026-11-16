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
//     stands for and a slow-down; the picture names the run, says that it loops and gives
//     the loop's length in the cell's time;
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
import { readLoop, loopAt, loopStreams, loopToken, loopRates, planFromLoop, loopWords, closesWords } from "./loop.js";
import { Tokens } from "./marks/tokens.js";
import { fitOnRow } from "./statement.js";
import { SLOWS, statementOf, tokenWords, timeWords, STILL_WORDS, HEAD_WORDS } from "./marks/beads.js";
import { ionColours } from "./ions.js";
import { clock } from "../replay/format.js";
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
export function seatsOf(kind, cell, mode) {
  const size = SIZES[mode], spots = cell?.spots, outline = cell?.frame?.outline;
  if (!size || !spots || !outline) return [];
  const cut = cell.frame.cut, reach = size.reach;
  const across = (angle, from, to, y) => ({ inward: (lateral = 0) => (share) => outline.walk(angle, lateral, from + (to - from) * share, y) });
  if (kind === "channels") return spots.channels.map((angle) => across(angle, reach * 0.9, -reach * 1.1, cut + size.over.channels));
  if (kind === "membrane") return (spots.charges || []).map((angle) => across(angle, reach * 0.9, -reach * 1.1, cut + size.over.membrane));
  if (kind === "pumps") return spots.pumps.map((angle) => across(angle, reach * 0.9, -reach * 1.2, cut + size.over.pumps));
  // A junction joins the cell to its first neighbour: "into the cell" is from the neighbour, across the cleft.
  if (kind === "junctions") return spots.junction === null || spots.junction === undefined ? [] : [across(spots.junction, (spots.gap || 0) + reach * 0.9, -reach * 0.9, cut + size.over.junctions)];
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
 * gives each stream one lane, the lanes dealt over the seats in turn, so that as many
 * beads pass as the run's rate says. Lanes that share a seat run side by side, `pitch` apart.
 */
export function arrange(kind, seats, { every, pitch }) {
  if (!seats.length) return [];
  const at = seats.map(() => []);
  const lanes = kind.groups.flatMap((group) => group.lanes);
  lanes.forEach((lane, index) => {
    const places = every ? (lane.spots ? lane.spots.filter((spot) => spot < seats.length) : seats.map((_, spot) => spot)) : [index % seats.length];
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
    this.slow = 1; // a run opens at true speed
    this.loops = new Map(); // species id -> its looping run, read
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

  /** The species' own looping run as read, or null. */
  get loop() {
    return (this.species?.id && this.loops.get(this.species.id)) || null;
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
   * Returns { ok } or { ok: false, why }: a run that is refused changes nothing, and the
   * species keeps illustration. No species names such a run yet; the page does not call this.
   */
  setLoop(speciesId, run) {
    const read = readLoop(run, speciesId);
    if (!read.ok) return read;
    // From here on the species has a run, and illustration is no longer shown for it (rule 11), even where
    // nothing of the run can be read yet: everything is then withheld, with the reason. `needs` names the
    // files of records to fetch before calling this again.
    const streams = loopStreams(read.loop);
    this.loops.set(speciesId, { ...read.loop, streams: streams.streams, busiest: streams.busiest, unread: streams.ok ? null : streams.why });
    this.build();
    this.refresh(true);
    return streams.ok ? { ok: true } : { ok: true, reads: false, why: streams.why, needs: streams.needs };
  }

  /** Work out what flows for the species and size mode shown. The lens calls this when it has built its cells. */
  build() {
    const loop = this.loop;
    const has = (part) => this.offers(part);
    if (loop) {
      this.source = { kind: "run", loop };
      this.plan = planFromLoop(this.flux, loop, loop.streams, { has, unread: loop.unread });
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

  setSlow(slow) {
    if (!SLOWS.includes(slow) || slow === this.slow) return;
    this.slow = slow;
    this.refresh(true);
    this.lens.onChrome?.();
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
    const signature = [this.species?.id, lens.sizeMode, this.source.kind, this.slow, palette.dark ? 1 : 0, palette.bg, ...showing.kinds.map((kind) => kind.id)].join("|");
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
      const laid = (item) => ({ key: item.key, lane: item.lane, path: item.path, reverse: item.reverse, colour: new THREE.Color(this.colourOf(item.lane)), perSecond: run ? 0 : PACE });
      const draw = (lanes, radius, home, dust) => {
        if (!lanes.length) return;
        const tokens = new Tokens({ lanes, radius, ground });
        home.root.add(tokens.group);
        this.tokens.push({ tokens, zone: home, dust, lanes });
      };
      const lanes = [];
      for (const kind of showing.kinds) {
        lanes.push(...arrange(kind, seatsOf(kind.id, this.cell, lens.sizeMode), { every: !run, pitch: kind.id === "junctions" ? size.bridge : size.pitch }).map(laid));
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
    const showing = Boolean(this.lens.active) && this.tokens.length > 0;
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
    if (!this.tokens.length) return null;
    const still = this.still();
    if (this.source.kind === "illustration") {
      const [notice, form] = illustrationWords(this.flux, still);
      return { notice, ways: [form, form.replace(" and their pace ", "\nand their pace "), form.replace(": ", ":\n").replace(" and their pace ", " and their pace\n").replace(" · ", "\n")] };
    }
    const loop = this.loop, at = loopAt(loop, this.elapsed);
    const what = this.showing().kinds[0]?.token || "ion";
    const lines = [loopWords(loop, this.species.label, clock), statementOf({ token: loopToken(loop.busiest, this.slow), what, speed: 1 / this.slow, interval: at.interval, clock, still })].join("\n");
    return { notice: null, ways: [lines, lines.replace(/ · /g, "\n")] };
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
    this.words();
  }

  /** Write the picture's statement into its labels, or hide them. */
  words() {
    const tags = this.tags;
    if (!tags) return;
    this.said = this.statement();
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
        keys.push({ key: "bead", text: `${tokenWords(loopToken(loop.busiest, this.slow), what)}. More beads a second means more of them a second; how fast a bead travels stands for nothing` });
        keys.push({ key: "time", text: `${timeWords(1 / this.slow)}. The run loops: ${clock(loop.length)} of the cell's time, then again from its start${still ? `. ${STILL_WORDS}` : ""}` });
        keys.push({ key: "way", text: "A bead goes the way its total grew over the interval shown, by the run's own signs" });
        keys.push({ key: "head", text: HEAD_WORDS });
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
    const time = run && flowing ? { label: "Speed", options: SLOWS.map((value) => ({ id: value, label: value === 1 ? "True" : `1/${value.toLocaleString("en-US")}`, title: timeWords(1 / value), on: this.slow === value })) } : null;
    const cannot = showing.withheld.map((item) => ({ id: item.id, label: item.label, why: item.why }));
    return {
      title: "Flux",
      // An illustration says so for as long as it shows (rule 11).
      example: flowing && !run ? flux.illustration.notice : null,
      rows: [{ channel: "motion", label: "Show", options: [{ label: "Off", off: FLUX_SWITCH, on: !this.on }, { id: FLUX_SWITCH, label: "All", on: this.on, title: "Show all that flows in this cell" }] }],
      time,
      // While nothing flows the cell's own drops, signals and ions move (a chosen part that draws nothing included): the
      // picture's own motion, which the page says is no measured flow, wherever motion is allowed.
      hint: flowing ? null : [cannot.length ? null : "Or choose a part to see its flux.", still ? null : REST_WORDS].filter(Boolean).join(" ") || null,
      keys,
      cannot,
      // The view's card stands just above the legend: the signs, what is not drawn and the door to the panel keep to one line.
      compact: flowing ? "What the beads mean" : "Why nothing is drawn here",
      // With the switch on and no part chosen, a panel says what stands behind all of it; a chosen part's own panel says it of that part.
      details: flowing && !showing.kinds.some((kind) => kind.part === showing.part) ? FLUX_PANEL : null,
    };
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
    return {
      id,
      kind: "flux",
      group: "biology",
      label: "What flows in this cell",
      eyebrow: "Flux",
      chips: [{ label: run ? "From the looping run" : flux.illustration.notice, title: run ? "The species' own run, made by the engine and packaged to loop" : "Nothing here is a number from a run" }],
      plain: run
        ? `${loopWords(this.loop, name, clock)}. ${this.loop.closes.says.replace(/\.?$/, ".")} ${closesWords(this.loop)}.${this.loop.follows.length ? " Where the loop follows a daughter cell, the beads are still read for its first cell: the hand-over is not drawn yet." : ""}`
        : `${flux.illustration.notice}. ${name} has no looping run of its own cell, so what flows is shown as illustration. ${forms["direction only"].says}.`,
      note: run ? "Every rate is a mean between two records that both lie inside the loop: no difference is taken across the seam." : flux.illustration.speaks_for,
      sections: [
        { title: "Drawn", note: "Where a lane runs is the picture's choice: the engine has no place for a single channel or pump.", items: drawn },
        { title: "Not drawn", items: plan.withheld.map((item) => ({ label: item.label, lines: [item.why] })) },
        ...(run
          ? [{ title: "Over the interval shown", items: this.readings().map((rate) => ({ label: [rate.stream.name, rate.stream.species].filter(Boolean).join(" · "), detail: rate.ions === null ? "no rate" : `${Math.round(rate.ions).toLocaleString("en-US")} a second ${rate.out === null ? "" : rate.out ? "out of the cell" : "into the cell"}`.trim(), lines: [`${rate.perSecond.toFixed(2)} beads a second, one bead being ${rate.token.toLocaleString("en-US")}`] })) }]
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
    if (!kinds.length && !withheld.length) return entity;
    const run = this.source.kind === "run";
    const items = [...kinds.flatMap((kind) => kind.groups.map((group) => this.item(kind, group))), ...withheld.map((item) => ({ label: `${item.label}: not drawn`, lines: [item.why] }))];
    const title = run ? "Flux, from the looping run" : `Flux. ${this.flux.illustration.notice}`;
    const note = run ? loopWords(this.loop, this.species.label, clock) : kinds.length ? `${this.flux.illustration.forms["direction only"].says}.` : null;
    return { ...entity, sections: [...(entity.sections || []), { title, note, items }] };
  }

  dispose() {
    this.clear();
  }
}

/** Where a law was read, for a test or a tool that lists the declarations. */
export const cited = (law) => (FLUX ? citation(FLUX, law) : null);
