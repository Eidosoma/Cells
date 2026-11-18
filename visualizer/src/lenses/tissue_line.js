// The gap-junction example's tumour tissue, in the Experiments tab (src/ui/viewer.js, showPart; the example opens on
// it): the runs in view under one clock, each a tissue of cells drawn as the Experiments view draws a run's cells
// (src/layers/sheet.js: each cell a flat prism of its polygon, standing where the run's view places it), the tumour
// outlined, each cell coloured by the quantity the experiment's driver states beside the run (miR200 minus Zeb
// mRNA) on a scale broken at its criterion's thresholds, with three dots on it, its saved amounts of the switch's
// three molecules; between two cells the junction, and through it, as the page's beads, the miR200 the run
// saved as carried there (src/layers/marks/stream.js, the Transfers layer's own drawing). Beside each tissue its whole
// run as a space-time map, with the clock across it.
//
// The clock follows the action (src/replay/tissue_play.js): each stated state change of the runs in view is held on
// the screen, the hours between pass quickly; the timeline's marks are the changes, each named, and a changed cell is
// ringed and named while its record shows. With less motion nothing plays by itself.
//
// It shows what the runs saved and what the driver states: nothing is interpolated, no state is read from a colour, no
// count and no front is worked out. A cell's state is the driver's, in the driver's word. A pick an engine check
// refused stands in its place in the parameter's order, named, with nothing drawn in it.

import * as THREE from "../three.js";
import { disposeTree } from "../core/stage.js";
import { loadRun, loadPart } from "../replay/source.js";
import { Player } from "../replay/player.js";
import { Catalogue, RUN } from "../replay/catalogue.js";
import { clock, duration, number, reading, unitSign } from "../replay/format.js";
import { lineOf, unionClock, Breaks, rangeOf, timeAxis, bands, TIME_SCALES, partsOf } from "../replay/tissue_line.js";
import { changesOf, Schedule, followBase, marksOf, FOLLOW, DWELL } from "../replay/tissue_play.js";
import { buildCells } from "../layers/sheet.js";
import { worldOf } from "../layers/world.js";
import { paint } from "../layers/marks/tint.js";
import { raise } from "../layers/marks/relief.js";
import { MARKS } from "../layers/marks/index.js";
import { declared } from "../layers/records.js";
import { readTissueColours } from "../ui/tissue_styles.js";
import { mountPartStyles } from "../ui/tissue_part.js";
import { h } from "../ui/dom.js";

export const CELL_ID = "tissue:"; // a cell of a run: `tissue:<arm>:<cell index>`
const PITCH = 10; // the scene's unit is the view's micrometre; where a view gives no geometry, cells stand 10 apart
const POLAR = 1e-4; // the camera's tilt from straight down: the tissues seen from straight above, their rows level
const BESIDE = 0.5; // a group beside the part's own tissues is drawn this much smaller: the part's own come first
const lower = (text) => (text ? text.charAt(0).toLowerCase() + text.slice(1) : "");

/** The lens for a part of an example, with its styles mounted once (the page's tokens and the viewer's shadow rules). */
export function makeTissueLens(stage, model, labels, partId, { root = null, document = globalThis.document, back = null, open = null } = {}) {
  mountPartStyles(root, document);
  return new TissueLineLens(stage, model, labels, partId, { back, open });
}

export class TissueLineLens {
  constructor(stage, model, labels, partId, { back = null, open = null } = {}) {
    this.id = "experiments";
    this.open = open; // shows another part of the example in this one's place (src/ui/viewer.js, showPart)
    this.back = back; // gives the tab to the example's networks (src/ui/viewer.js, showExample), from the card's own button
    this.partId = partId;
    this.stage = stage;
    this.model = model;
    this.labels = labels;
    this.catalogue = new Catalogue(model.raw.replays);
    this.line = lineOf(model.raw.replays, partId);
    this.player = new Player();
    this.root = new THREE.Group();
    this.root.name = "tissue";
    this.wantsLeftRoom = true; // framed in the room the cards on the left leave it (src/ui/viewer.js, renderPanel)
    this.active = false;
    this.loading = true;
    this.error = null;
    this.runs = []; // [{ group, slot, run, record, states, amounts, moved, routes, cells, lined }]
    this.groups = []; // the part's own tissues, and a part beside them (groupsOf)
    this.blocks = []; // each group as laid out (build)
    this.changes = [];
    this.marks = [];
    this.scale = TIME_SCALES[0][0];
    this.selected = null; // { arm, cell }
    this.hovered = null;
    this.panel = null;
    this.autoplayed = false;
    this.colours = readTissueColours(stage?.host);
    this.ink = new THREE.Color();
    this.soft = new THREE.Color();
    this.player.addEventListener("time", () => {
      this.draw();
      this.stage?.invalidate();
    });
    this.player.addEventListener("state", () => {
      for (const piece of this.pieces?.values() || []) piece.stream?.retime();
      this.draw();
      this.onChrome?.();
      this.stage?.invalidate();
    });
    this.ready = this.load();
  }

  // ------------------------------------------------------------ the runs

  /**
   * The tissues this view draws: the part's own runs, and, where its entry puts another part beside it (`tissue.beside`,
   * the picture's choice), that part's runs under them, with its own words. Each { id, line, front, role, caption }.
   */
  groupsOf() {
    if (!this.line) return [];
    const tissue = this.line.entry.tissue || {};
    const groups = [{ id: this.line.id, line: this.line, front: tissue.front, role: "main", caption: tissue.caption || null }];
    const beside = tissue.beside;
    const other = beside?.part ? lineOf(this.model.raw.replays, beside.part) : null;
    if (other) groups.push({ id: other.id, line: other, front: beside.front, role: "beside", caption: beside.says || other.short, frontSays: beside.front_says || null });
    return groups;
  }

  /** The example's other part whose entry gives a caption of its own (the sheet, from the line), to open from the picture; null where none. */
  door() {
    if (typeof this.open !== "function" || !this.line) return null;
    return partsOf(this.model.raw.replays, this.line.entry.part_of).find((part) => part.id !== this.line.id && part.tissue?.caption) || null;
  }

  /** A group's arms in view: those its entry puts in front (the picture's choice), unless the visitor asked for all. */
  armsInView(group) {
    const all = group.line.runs.map((slot) => slot.arm);
    return this.everyArm || !Array.isArray(group.front) || !group.front.length ? all : all.filter((arm) => group.front.includes(arm));
  }

  /** Whether some group shows fewer arms than it has: the card then offers them all. */
  someLeftOut() {
    return this.groups.some((group) => Array.isArray(group.front) && group.front.length && group.front.length < group.line.runs.length);
  }

  /** Show every arm, or only those in front: the arms not yet loaded are fetched as they come into view. */
  setEveryArm(on) {
    if (Boolean(on) === Boolean(this.everyArm)) return;
    this.everyArm = Boolean(on);
    this.loading = true;
    this.onChrome?.();
    this.ready = this.load().then(() => {
      if (this.active) this.enter();
    });
  }

  async load() {
    try {
      if (!this.line) throw new Error(`the catalogue has no tissue called ${this.partId}`);
      this.loaded ??= new Map();
      const concentrations = (run) => [...run.records.values()].filter((item) => item.stated?.format === "cells.experiment_quantity@1" && item.set === "cell" && item.axes.length === 2);
      const wanted = (group) => [group.line.entry.opens?.record].flat().filter((id) => typeof id === "string");
      // Each arm in view, fetched once: its run, and of its records in files of their own only what the tissue draws.
      const open = async (group, slot) => {
        const key = `${group.id}/${slot.arm}`;
        if (this.loaded.has(key)) return this.loaded.get(key);
        const run = await loadRun(slot.row);
        const record = wanted(group).map((id) => run.records.get(id)).find((item) => item && item.set === "cell" && item.marks?.length);
        if (!record) throw new Error(`the run ${slot.arm} has no stated quantity with a criterion to colour its cells by`);
        const species = speciesWords(group.line);
        const stated = concentrations(run);
        const want = [...(stated.length ? [] : species.map((item) => `amount.${item.id}`)), ...species.map((item) => `passive_transferred.${item.id}`)];
        for (const part of new Set(want.map((id) => run.pending.get(id)?.part).filter(Boolean))) await loadPart(run, part);
        // The switch's three molecules: the concentrations the driver states beside the run (µM), else the run's saved amounts.
        const amounts = stated.length ? stated.map((item) => ({ id: item.id, label: headOf(item.label), record: item, stated: true })) : species.map((item) => ({ ...item, record: run.records.get(`amount.${item.id}`) || null }));
        const moved = species.map((item) => run.records.get(`passive_transferred.${item.id}`)).find((item) => item && !allStill(run, item)) || null;
        const cells = cellsOf(run);
        const item = { group, slot, run, record, states: record.states ? run.records.get(record.states) || null : null, amounts, moved, routes: Boolean(run.sets.get("passive_route")), cells, lined: isLine(run) };
        this.loaded.set(key, item);
        return item;
      };
      this.groups = this.groupsOf();
      const opened = await Promise.all(this.groups.flatMap((group) => group.line.runs.filter((slot) => this.armsInView(group).includes(slot.arm)).map((slot) => open(group, slot))));
      const arms = opened.map((item) => item.slot.arm);
      if (new Set(arms).size !== arms.length) throw new Error("two runs in view have the same arm");
      this.runs = opened;
      // One clock for the runs in view: the union of their saved times (each shows its own record at or before it, and
      // a run that ended before the clock shows its last record, said so on the picture).
      this.clock = unionClock(this.runs.map((item) => item.run));
      const { low, high } = rangeOf(this.runs.map((item) => item.record));
      this.breaks = new Breaks(this.runs[0].record.marks, low, high, this.colours);
      // The play: the union of the stated changes of the runs in view, and the clock that follows it. A line's cell is
      // named by its number along the line, a sheet's by the run's own id.
      this.changes = changesOf(this.runs.map((item) => ({ arm: item.slot.arm, label: item.slot.short, run: item.run, states: item.states, naming: item.lined ? "number" : "id" })));
      this.schedule = new Schedule(this.clock.t, this.changes);
      this.marks = marksOf(this.changes);
      // Each molecule's dots reach their full size at its largest amount in the runs in view (the records' own ranges).
      const molecules = [...new Set(this.runs.flatMap((item) => item.amounts.map((amount) => amount.id)))];
      this.most = Object.fromEntries(molecules.map((id) => [id, Math.max(1e-30, ...this.runs.map((item) => item.amounts.find((amount) => amount.id === id)?.record?.range?.[1] ?? 0))]));
      this.player.load(this.clockOf());
      if (Number.isFinite(this.pendingTime)) this.player.seek(this.pendingTime);
      this.pendingTime = null;
      this.loading = false;
      this.build();
      if (this.active) this.enter();
      this.onChrome?.();
      this.onPanel?.();
    } catch (error) {
      this.loading = false;
      this.error = String(error?.message || error);
      this.onChrome?.();
    }
    return this;
  }

  /** The clock the page's timeline and the player keep: the first run's times, with the play's schedule and its marks. */
  clockOf() {
    const run = this.runs[0].run, marks = this.marks, base = followBase(this.schedule);
    const clockRun = Object.create(this.clock);
    Object.assign(clockRun, {
      id: `${this.partId}--clock`,
      timeBase: base,
      events: marks.map((mark) => ({ time: mark.time, label: mark.label })),
      eventsBy: (time) => marks.filter((mark) => mark.time <= time + 5e-4).length,
      validity: null,
      isValid: () => true,
      info: { ...run.info, judged_s: null },
    });
    return clockRun;
  }

  /** The run's seconds that pass each second of watching now: the play's where it follows the changes, else the speed chosen. */
  rate() {
    return this.player.speed === FOLLOW ? this.schedule.rateAt(this.player.time) : this.player.speed;
  }

  /** The maps' time axis: logarithmic about a two-hundredth of the run (the picture's choice), or even. */
  axis() {
    return timeAxis(this.clock.start, this.clock.end, { scale: this.scale, step: (this.clock.end - this.clock.start) / 200 });
  }

  // ------------------------------------------------------------ layout and drawing

  /** The room the picture has: the stage less the cards on the left, a panel or chart on the right, the bar above and the timeline below. */
  room() {
    const { stage } = this;
    const narrow = stage.width < 760;
    // The page leaves room at the left and the right only on a wide window (src/ui/viewer.js, renderPanel).
    // On a narrow window the panel's sheet lies over the picture's foot: the layout keeps the room it had without it.
    const { right = 0 } = stage.insets || {}, bottom = narrow ? 0 : stage.insets?.bottom || 0, left = narrow ? 0 : stage.insets?.left || 0;
    const top = narrow ? 116 : 70, foot = narrow ? 180 : 104, margin = narrow ? 10 : 16;
    return { width: Math.max(120, stage.width - left - (narrow ? 0 : right) - 2 * margin), height: Math.max(120, stage.height - top - foot - bottom), top, foot, left, right, bottom, margin, narrow };
  }

  /**
   * Lay the tissues out in the room the page leaves the picture, seen from straight above, so that every name has its own
   * place and none lies on a cell or on another name. The names are measured first (their size is the page's, in
   * pixels, whatever the picture's scale); then the scale is the largest at which the tissues and their names fit the
   * room; then each thing stands where the layout puts it, a pixel being 1/scale of the scene's unit. Groups stand one
   * under the other: the part's own tissues, then a group beside them (smaller). Lines stand one above the other, each
   * with its whole run as a map beside it (under it on a narrow window); sheets stand three to a row.
   */
  build() {
    this.dropPieces();
    this.labels.clear();
    this.tags = null;
    disposeTree(this.root);
    this.root.clear();
    if (!this.runs.length || !this.active) return;
    const narrow = this.stage.width < 760;
    this.narrow = narrow;
    const palette = this.stage?.palette || {};
    this.ink.set(palette.fg || "#12283a");
    this.soft.set(palette.muted || "#566878");
    this.axisNow = this.axis();
    const bandsOf = (run) => bands(Array.from(run.t), this.axisNow);
    this.pieces = new Map();
    const frameColour = new THREE.Color(this.colours.frame);
    const room = this.room();
    // A little short of the room: the camera's fit may leave a hair less than it.
    const roomWidth = room.width * 0.97, roomHeight = room.height * 0.97;
    const tags = (this.tags = { chosen: null, changes: [], changeKey: null, ended: [], caption: null, made: [] });
    const made = (kind, parts, { maxWidth = null, title = null } = {}) => {
      const label = this.labels.add({ text: "", anchor: new THREE.Vector3(), kind, priority: 9, lift: 0 });
      label.element.replaceChildren(...parts.filter((part) => part !== null && part !== undefined && part !== ""));
      if (title) label.element.title = title;
      label.boost = 1000;
      tags.made.push(label);
      fit(label, maxWidth);
      return label;
    };
    const fit = (label, maxWidth) => {
      label.element.style.maxWidth = maxWidth ? `${Math.max(40, Math.floor(maxWidth))}px` : "";
      label.width = label.element.offsetWidth;
      label.height = label.element.offsetHeight;
    };
    const line = (words, kind = "") => h("span", { class: `tissue-line${kind ? ` ${kind}` : ""}` }, words);

    // The tissues, built at the scene's origin; placed when the layout is known.
    const blocks = [];
    for (const group of this.groups) {
      const rows = group.line.slots
        .filter((slot) => (slot.kind === "refused" ? group.role === "main" : this.runs.some((item) => item.slot === slot)))
        .map((slot) => {
          if (slot.kind === "refused") return { slot, group };
          const item = this.runs.find((run) => run.slot === slot);
          const sheet = buildCells(item.run, { pick: (k) => `${CELL_ID}${slot.arm}:${k}` });
          const thick = 0.34 * sheet.pitch;
          raise(sheet, () => thick);
          const across = 2 * sheet.extent, deep = 2 * Math.max(...sheet.cells.map((cell) => Math.abs(cell.centre[1]) + cell.radius));
          return { slot, group, item, sheet, thick, across, deep };
        });
      if (!rows.some((row) => row.sheet)) continue;
      // With every arm in view the sheet's group stands alone: the line beside it is folded away (the card opens it).
      if (group.role === "beside" && this.everyArm) continue;
      const lined = rows.filter((row) => row.sheet).every((row) => row.item.lined);
      blocks.push({ group, rows, lined, role: group.role, scale: group.role === "beside" ? BESIDE : 1 });
    }

    // The names, measured. A line: its value and place, and its end words (and no routes); a sheet: its place, and its
    // value in small type where it fits, over it, and its end words under it; a group's words over it.
    const placeSays = this.line.entry.tissue?.place_says;
    for (const block of blocks) {
      const { group } = block;
      if (block.role === "main" && group.caption) block.caption = made("tissue-caption", [group.caption], { maxWidth: Math.min(roomWidth, 640) });
      else if (block.role === "main" && this.door()) {
        // From the line: the sheet's door, small, at the picture's top right (its caption is in the card's block).
        const other = this.door();
        block.door = made("tissue-door", [h("button", { class: "tissue-back tissue-door-button", type: "button", dataset: { part: other.id }, onclick: () => this.open(other.id) }, other.short || other.label)], { title: other.tissue.caption });
      } else if (block.role === "beside") block.caption = made("tissue-group", [group.caption], { maxWidth: roomWidth });
      // Over a sheet's grid, once: what x2 is (the record's words), and where its own threshold lies (the dashed line).
      if (!block.lined && block.role === "main") {
        const bracket = group.line.entry.tissue?.bracket;
        const shown = (bracket?.between || []).every((arm) => block.rows.some((row) => row.slot.arm === arm && row.sheet));
        const over = [placeSays ? `Each place is against x2, ${placeSays} (section 7.6).` : null, bracket && shown ? `The dashed line: ${lower(bracket.says)}.` : null].filter(Boolean);
        // The sheets' records end before the clock's (at 2,000 s): past that, each shows its last record, said once here.
        const ends = [...new Set(block.rows.filter((row) => row.sheet && row.item.run.end < this.clock.end - 1e-6).map((row) => row.item.run.end))];
        const early = ends.length === 1 ? `Past ${clock(ends[0])} each sheet shows its last record: its run's record ends there.` : null;
        if (over.length || early) {
          block.over = made("tissue-over", [...over.map((words) => line(words)), early ? line(early, "is-early") : null], { maxWidth: roomWidth });
          if (early) tags.ended.push({ tag: block.over, end: ends[0] });
        }
      }
      // A key over the part's own tissues, in sight on the picture: the three dots in a cell, and a bead (on a phone, over
      // a line; a sheet's phone screen has no room for it beside its caption, and the legend holds it).
      if (block.role === "main" && !(narrow && !block.lined)) {
        const first = block.rows.find((row) => row.sheet)?.item;
        const molecules = (first?.amounts || []).filter((amount) => amount.record);
        const dot = (colour, kind = "") => h("span", { class: `tissue-key-dot${kind}`, style: `background:${colour}` });
        const parts = [];
        if (molecules.length) parts.push(h("span", { class: "tissue-key-item" }, ...molecules.map((amount, m) => dot(this.colours.molecules?.[m] || "#888888")), ` ${molecules.map((amount) => amount.label).join(", ")}${molecules[0].stated ? " (µM, as stated)" : ""}: a dot's area, its share of the largest`));
        if (this.runs.some((item) => item.moved)) parts.push(h("span", { class: "tissue-key-item" }, dot(this.streamColours().ionCss(), " is-bead"), ` a bead: ${speciesWords(group.line).find((item) => item.id === this.runs.find((run) => run.moved)?.moved.species)?.label || "what crosses"} carried across`));
        if (parts.length) block.key = made("tissue-key", parts, { maxWidth: roomWidth });
      }
      for (const row of block.rows) {
        const { slot } = row;
        if (!row.sheet) {
          row.head = made("tissue-refused", [`${slot.label} · ${lower(group.line.refusedWords)}`], { maxWidth: roomWidth });
          continue;
        }
        const quiet = !row.item.routes && group.line.entry.tissue?.no_routes ? group.line.entry.tissue.no_routes.replace(/^D = 0: /, "") : null;
        const early = block.lined && row.item.run.end < this.clock.end - 1e-6 ? `shows its last record (${clock(row.item.run.end)})` : null;
        if (block.lined) {
          // A line beside the part's own stands two to a row: on a narrow window its words wrap to half the room.
          const half = block.role === "beside" && narrow ? (roomWidth - 24) / 2 : null;
          row.head = made(`tissue-head${half ? " is-wrap" : ""}`, [[slot.label, where(slot, block.role === "beside" ? null : placeSays)].filter(Boolean).join(" · ")], { maxWidth: half });
          row.end = slot.end || quiet || early ? made(`tissue-end${half ? " is-wrap" : ""}`, [slot.end ? line(slot.end) : null, quiet ? line(quiet) : null, early ? line(early, "is-early") : null], { maxWidth: half }) : null;
        } else {
          row.head = made("tissue-head is-stacked", [line(where(slot, null) || slot.label, "is-place"), where(slot, null) ? line(slot.label, "is-value") : null]);
          row.end = slot.end || quiet || early ? made("tissue-end is-stacked", [slot.end ? line(slot.end) : null, quiet ? line(quiet) : null, early ? line(early, "is-early") : null]) : null;
        }
        if (row.end && early) tags.ended.push({ tag: row.end, end: row.item.run.end });
      }
    }
    // A change's name and a chosen cell's, as tall as they are drawn (each is made when it shows: placeTags).
    const sample = made("tissue-change", ["cell 25: M to X"]);
    const calloutHeight = sample.height;
    this.labels.remove(sample);
    tags.made.splice(tags.made.indexOf(sample), 1);
    const chosenHeight = calloutHeight;
    // Times down a map, as tall and as wide as the widest is drawn.
    let tickHeight = 0, tickWidth = 0;
    for (const words of new Set([...this.axisNow.ticks.map((tick) => tick.words), duration(this.axisNow.end - this.axisNow.start)])) {
      const sample = made("tissue-tick", [words]);
      tickHeight = Math.max(tickHeight, sample.height);
      tickWidth = Math.max(tickWidth, sample.width);
      this.labels.remove(sample);
      tags.made.splice(tags.made.indexOf(sample), 1);
    }

    /**
     * The layout at a scale (pixels for each of the scene's units, the part's own; a group beside it at BESIDE of that):
     * each block's size in pixels and, for each thing, its place in pixels from the block's top left.
     */
    const GAP = 10, ROW = 8, SIDE = 22;
    const layout = (scale, final = false) => {
      let width = 0, height = 0;
      for (const block of blocks) {
        const s = scale * block.scale;
        let y = 0, w = 0;
        const top = (label) => {
          if (!label) return;
          label.at = { x: null, y };
          y += label.height + 4;
          w = Math.max(w, label.width);
        };
        top(block.caption);
        // The door to the other part stands at the top right: beside the first line's names where the maps leave room there.
        // (Where the door is no wider than the maps' column, which stands over no name of the lines.)
        const doorBeside = block.door && block.lined && block.role === "main" && !narrow && block.door.width <= 24 + 104 + 4 + tickWidth;
        if (block.door) {
          block.door.at = { x: "right", y };
          if (!doorBeside) y += block.door.height + 6;
        }
        top(block.over);
        top(block.key);
        if (block.lined) {
          // Lines one above the other; on a wide window of the part's own, each with its map beside it; on a narrow one, under it.
          // On a narrow window the maps are left out: the room goes to the cells (the timeline's marks keep the changes).
          const mapsBeside = block.role === "main" && !narrow, mapsUnder = false;
          const columns = block.role === "beside" ? 2 : 1;
          const mapWidth = mapsBeside ? 104 : 0;
          const itemWidth = (row) => Math.max(row.sheet ? row.across * s : 0, row.head?.width || 0, row.end && !sideBySide(row) ? row.end.width : 0);
          const sideBySide = (row) => !row.end || (row.head?.width || 0) + row.end.width + 16 <= (row.sheet ? row.across * s : 0);
          const colWidth = Math.max(...block.rows.map(itemWidth)) + (mapsBeside ? SIDE + mapWidth + 4 + tickWidth : 0);
          let column = 0, rowTop = y, rowHeight = 0;
          for (const [n, row] of block.rows.entries()) {
            let ry = rowTop;
            const left = column * (colWidth + SIDE);
            row.at = { left, y: ry };
            // The first line's names stand level with the door, at least as low as its foot.
            if (n === 0 && doorBeside) ry += Math.max(0, block.door.height - (row.head?.height || 0));
            if (!row.sheet) {
              row.head.at = { x: left + row.head.width / 2, y: ry };
              ry += row.head.height + ROW;
            } else {
              const lineWidth = row.across * s;
              row.head.at = { x: left + row.head.width / 2, y: ry };
              if (row.end && sideBySide(row)) row.end.at = { x: left + lineWidth - row.end.width / 2, y: ry };
              ry += row.head.height + 2;
              if (row.end && !sideBySide(row)) {
                row.end.at = { x: left + row.end.width / 2, y: ry };
                ry += row.end.height + 2;
              } else if (row.end) ry = Math.max(ry, row.end.at.y + row.end.height + 2);
              ry += 2;
              row.cellsAt = { x: left + lineWidth / 2, y: ry + (row.deep * s) / 2 };
              const cellsTop = ry;
              ry += row.deep * s;
              // Under the cells: a row for a change's name and the chosen cell's (side by side where both show: placeTags).
              row.calloutY = ry + 3;
              row.chosenY = ry + 3;
              ry += 3 + Math.max(calloutHeight, chosenHeight) + 2;
              if (mapsBeside) {
                const mapHeight = Math.max(3 * tickHeight, ry - cellsTop);
                row.mapAt = { x: left + lineWidth + SIDE, y: cellsTop, width: mapWidth, height: mapHeight };
                ry = Math.max(ry, cellsTop + mapHeight + tickHeight / 2 + 2);
              } else if (mapsUnder) {
                const mapHeight = Math.max(3 * tickHeight, 44);
                row.mapAt = { x: left + (lineWidth - mapWidth) / 2, y: ry + tickHeight / 2, width: mapWidth, height: mapHeight };
                ry += mapHeight + tickHeight + 4;
              }
            }
            rowHeight = Math.max(rowHeight, ry - rowTop);
            w = Math.max(w, left + colWidth);
            if (++column >= columns) {
              column = 0;
              rowTop += rowHeight + ROW;
              rowHeight = 0;
            }
          }
          if (column) rowTop += rowHeight + ROW;
          y = rowTop;
        } else {
          // Sheets three to a row; the gap between the two the threshold lies between is wide enough for its dashed line.
          const columns = Math.min(3, block.rows.length);
          const bracket = block.group.line.entry.tissue?.bracket?.between || [];
          const sheetWidth = Math.max(...block.rows.filter((row) => row.sheet).map((row) => row.across)) * s;
          // A name's value is drawn where it fits the sheet's width; the end words wrap to it.
          // A sheet's value stands under its place where it fits the sheet's width, and while the sheets stand in one row
          // (with every arm in view the room goes to the sheets; the values are in the card and each cell's panel).
          for (const row of block.rows) {
            if (!row.sheet) continue;
            const value = row.head.element.querySelector(".is-value");
            if (value) {
              value.hidden = false;
              value.hidden = block.rows.length > columns || value.offsetWidth > Math.max(sheetWidth, 96) + 1;
            }
            fit(row.head, null);
          }
          // The end words wrap to the column: as wide as its sheet or its widest name.
          const named = Math.max(sheetWidth, ...block.rows.map((row) => row.head?.width || 0));
          for (const row of block.rows) if (row.end) fit(row.end, Math.max(named, narrow ? 72 : 180));
          const colWidth = Math.max(named, ...block.rows.map((row) => row.end?.width || 0));
          // Between two columns: room for the dashed line, less on a narrow window.
          const between = narrow ? 14 : 2 * SIDE;
          const lines = [];
          block.rows.forEach((row, k) => (lines[Math.floor(k / columns)] ||= []).push(row));
          block.divider = null;
          for (const [n, rowsOf] of lines.entries()) {
            const headHeight = Math.max(...rowsOf.map((row) => row.head?.height || 0));
            const endHeight = Math.max(0, ...rowsOf.map((row) => row.end?.height || 0));
            const deep = Math.max(...rowsOf.filter((row) => row.sheet).map((row) => row.deep)) * s;
            rowsOf.forEach((row, k) => {
              const left = k * (colWidth + between);
              const middle = left + colWidth / 2;
              row.at = { left, y };
              row.head.at = { x: middle, y: y + headHeight - row.head.height };
              if (row.sheet) {
                row.cellsAt = { x: middle, y: y + headHeight + 4 + deep / 2 };
                if (row.end) row.end.at = { x: middle, y: y + headHeight + 4 + deep + 4 };
                row.calloutY = null;
              }
              w = Math.max(w, left + colWidth);
            });
            // The dashed line between the two arms the sheet's threshold lies between: between their columns in a row,
            // or between two rows where the second starts the next.
            const k1 = rowsOf.findIndex((row) => row.slot.arm === bracket[0]), k2 = rowsOf.findIndex((row) => row.slot.arm === bracket[1]);
            if (k1 >= 0 && k2 === k1 + 1) block.divider = { x: (k1 + 1) * (colWidth + between) - between / 2, y0: y + headHeight, y1: y + headHeight + 4 + deep };
            y += headHeight + 4 + deep + 4 + endHeight + ROW;
            const next = lines[n + 1];
            if (k1 === rowsOf.length - 1 && next && next[0]?.slot.arm === bracket[1]) {
              block.divider = { y: y + 3, x0: 0, x1: null };
              y += 8;
            }
          }
          if (block.divider && block.divider.x1 === null) block.divider.x1 = w;
        }
        block.size = { width: Math.max(w, block.caption?.width || 0, block.over?.width || 0, block.key?.width || 0, block.door?.width || 0), height: y };
        if (block.door) block.door.at.x = block.size.width - block.door.width / 2;
        for (const label of [block.caption, block.over, block.key]) if (label) label.at.x = block.size.width / 2;
        width = Math.max(width, block.size.width);
        height += y + (height ? GAP : 0);
      }
      return { width, height };
    };
    // The largest scale at which everything fits the room. Whether it fits is not one way in the scale (a line's end words
    // stand beside its name only where the line is long enough), so the scales are tried from the largest down, then the
    // one found is refined between it and the next larger tried. Where none fits, the one that leaves the least over.
    const fits = (scale) => {
      const { width, height } = layout(scale);
      return { ok: width <= roomWidth && height <= roomHeight, over: Math.max(width - roomWidth, 0) + Math.max(height - roomHeight, 0) };
    };
    let scale = null, upper = null, least = { over: Infinity, scale: 0.05 };
    for (let k = 0; k <= 120; k++) {
      const trial = 60 * Math.pow(0.02 / 60, k / 120);
      const tried = fits(trial);
      if (tried.ok) {
        scale = trial;
        break;
      }
      if (tried.over < least.over) least = { over: tried.over, scale: trial };
      upper = trial;
    }
    if (scale !== null && upper !== null) {
      let low = scale, high = upper;
      for (let k = 0; k < 12; k++) {
        const middle = Math.sqrt(low * high);
        if (fits(middle).ok) low = middle;
        else high = middle;
      }
      scale = low;
    }
    if (scale === null) scale = least.scale;
    const size = layout(scale, true);
    this.pxScale = scale; // pixels for each of the scene's units, the part's own

    // Each thing in the scene: a block's pixels from its top left are its units over the scale (its own, for a group
    // beside); the blocks stand centred, one under the other.
    let top = 0;
    const rows = [];
    for (const block of blocks) {
      const s = scale * block.scale;
      const root = new THREE.Group();
      root.position.set(0, 0, top / scale);
      root.scale.setScalar(block.scale);
      this.root.add(root);
      block.root = root;
      const unit = (px) => px / s;
      const xOf = (px) => unit(px - block.size.width / 2);
      block.unit = unit;
      block.xOf = xOf;
      const anchor = (label) => {
        // The label layer stands a label's middle bottom on its point.
        const point = root.localToWorld(new THREE.Vector3(xOf(label.at.x), 0, unit(label.at.y + label.height)));
        label.anchor.copy(point);
        label.local = { x: xOf(label.at.x), z: unit(label.at.y + label.height) };
      };
      root.updateMatrixWorld(true);
      for (const label of [block.caption, block.door, block.over, block.key]) if (label) anchor(label);
      for (const row of block.rows) {
        row.block = block;
        rows.push(row);
        if (row.head) anchor(row.head);
        if (row.end) anchor(row.end);
        if (!row.sheet) {
          const outline = dashedRect(xOf(row.at.left), xOf(row.at.left + row.head.width), unit(row.head.at.y), unit(row.head.at.y + row.head.height), frameColour);
          outline.userData.unpickable = true;
          root.add(outline);
          this.pieces.set(row.slot.arm, { row, refused: true });
          continue;
        }
        const { item, sheet, thick, slot } = row;
        const group = new THREE.Group();
        group.position.set(xOf(row.cellsAt.x), 0, unit(row.cellsAt.y));
        group.add(sheet.mesh);
        if (sheet.seams) group.add(sheet.seams.mesh);
        root.add(group);
        const surface = { cells: sheet.cells, geometry: sheet.geometry, links: sheet.seams ? sheet.seams.quads : [], pitch: sheet.pitch, low: sheet.low, high: sheet.high, extent: sheet.extent, root: group, outside: null, world: null };
        surface.world = worldOf(item.run, sheet.cells.map((cell, k) => ({ set: "cell", index: k, face: cell.face, ring: cell.ring, centre: cell.centre, radius: cell.radius })));
        const channels = channelMesh(item.run, sheet, thick, this.ink);
        if (channels) group.add(channels);
        const tumor = this.tumorOf(item, sheet);
        if (tumor) group.add(tumor.mesh);
        const dots = this.dotsOf(item, sheet, thick);
        if (dots) group.add(dots);
        // What the junctions' routes carried, as the page's beads (the Transfers layer's own drawing).
        let stream = null;
        if (item.moved) {
          const source = declared(item.run, item.moved.id);
          stream = MARKS.stream.create({ surface: { ...surface, pitch: 1.4 * sheet.pitch }, run: item.run, fed: { sources: [source] }, colours: this.streamColours(), strength: "bold", speed: () => this.rate(), paused: () => !this.player.playing, still: () => Boolean(this.stage?.reducedMotion) });
          // Each bead drawn large enough to read at the cells' size (its path stays from one cell's middle to the other's).
          stream.tokens?.setRadius?.(0.12 * sheet.pitch);
        }
        const rings = ringMesh(item.cells.count, this.colours.accent || "#1f6fd0");
        group.add(rings);
        const piece = { row, item, sheet, surface, group, stream, rings, dots, thick, tumor, board: null, map: null, cursor: null, column: null };
        if (row.mapAt) {
          // The whole run as a map, flat beside (or under) the line: the same cells across in the view's order, time running
          // down it, the clock across it; its times at its right edge.
          const mapWidth = unit(row.mapAt.width), mapDepth = unit(row.mapAt.height);
          const board = new THREE.Group();
          board.position.set(xOf(row.mapAt.x), 0, unit(row.mapAt.y));
          root.add(board);
          const mapAt = { x0: 0, z0: 0 };
          const bandsNow = bandsOf(item.run);
          const map = mapMesh(item, mapAt.x0, mapAt.z0, mapWidth, mapDepth, bandsNow, this.breaks);
          map.userData.pick = (hit) => {
            const local = board.worldToLocal(hit.point.clone());
            const cell = Math.min(item.cells.count - 1, Math.max(0, Math.floor(((local.x - mapAt.x0) / mapWidth) * item.cells.count)));
            return `${CELL_ID}${slot.arm}:${cell}`;
          };
          map.userData.recordAt = (hit) => {
            const local = board.worldToLocal(hit.point.clone());
            return this.timeAtShare((local.z - mapAt.z0) / mapDepth, item.run);
          };
          board.add(map);
          const mapFrame = rectLines(mapAt.x0 - unit(1), mapAt.x0 + mapWidth + unit(1), mapAt.z0 - unit(1), mapAt.z0 + mapDepth * (1 + (bandsNow[bandsNow.length - 1].to - 1)) + unit(1), frameColour, 0.03);
          mapFrame.userData.unpickable = true;
          board.add(mapFrame);
          const cursor = new THREE.Mesh(new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: this.ink, toneMapped: false, side: THREE.DoubleSide }));
          cursor.scale.set(mapWidth + unit(8), 1, unit(2));
          cursor.position.set(mapAt.x0 + mapWidth / 2, 0.06, mapAt.z0);
          cursor.userData.unpickable = true;
          board.add(cursor);
          const marker = rectLines(0, 1, 0, 1, this.ink, 0.07);
          marker.visible = false;
          marker.userData.unpickable = true;
          board.add(marker);
          Object.assign(piece, { board, map, mapAt, mapWidth, mapDepth, cursor, column: marker, bands: bandsNow });
          // Its times, a third of its depth apart at least (and a name's height), its end always.
          const kept = [], least = Math.max(0.3, (tickHeight + 2) / row.mapAt.height);
          for (const tick of this.axisNow.ticks) {
            if (tick.at === 1) while (kept.length > 1 && 1 - kept.at(-1).at < least) kept.pop();
            if (tick.at === 1 || !kept.length || tick.at - kept.at(-1).at >= least) kept.push(tick);
          }
          for (const tick of kept) {
            const label = made("tissue-tick", [tick.at === 1 ? duration(tick.time - this.axisNow.start) : tick.words]);
            label.at = { x: row.mapAt.x + row.mapAt.width + 4 + label.width / 2, y: row.mapAt.y + tick.at * row.mapAt.height - label.height / 2 };
            anchor(label);
          }
        }
        this.pieces.set(slot.arm, piece);
      }
      // The sheet's own threshold: a dashed line between the two arms it lies between.
      if (block.divider) {
        const d = block.divider;
        const from = d.x !== undefined ? new THREE.Vector3(xOf(d.x), 0.05, unit(d.y0)) : new THREE.Vector3(xOf(d.x0), 0.05, unit(d.y));
        const to = d.x !== undefined ? new THREE.Vector3(xOf(d.x), 0.05, unit(d.y1)) : new THREE.Vector3(xOf(d.x1), 0.05, unit(d.y));
        const mark = dashedLine(from, to, this.ink, unit(6), unit(4));
        mark.userData.unpickable = true;
        root.add(mark);
        this.bracket = { block, from, to };
      }
      block.top = top;
      top += block.size.height + GAP;
    }
    if (!blocks.some((block) => block.divider)) this.bracket = null;
    this.blocks = blocks;
    this.rows = rows;
    this.calloutHeight = calloutHeight;
    const half = (size.width / 2) / scale;
    this.box = { x0: -half, x1: half, z0: 0, z1: (top - GAP) / scale, y0: 0, y1: 0 };
    this.root.updateMatrixWorld(true);
    this.draw();
  }

  dropPieces() {
    for (const piece of this.pieces?.values() || []) piece.stream?.dispose();
    this.pieces = null;
  }

  /** The tumour's cells, as the record names them (the overlay's `tissue.tumor`), outlined by one band round them; null where none is named. */
  tumorOf(item, sheet) {
    const named = item.group.line.tumor?.cells || [];
    const indices = named.map((id) => item.cells.ids.indexOf(id)).filter((index) => index >= 0);
    if (!indices.length) return null;
    const pad = 0.2 * sheet.pitch;
    const hull = convexHull(indices.flatMap((k) => sheet.cells[k].ring.map(([x, y]) => [x, y])));
    // The hull pushed out by `pad`, drawn as a flat band on the ground round the tumour's cells.
    const outer = offsetRing(hull, pad), inner = offsetRing(hull, pad * 0.5);
    const positions = [], index = [];
    outer.forEach(([x, y], k) => positions.push(x, 0.04, y, inner[k][0], 0.04, inner[k][1]));
    for (let k = 0; k < outer.length; k++) {
      const a = 2 * k, b = 2 * ((k + 1) % outer.length);
      index.push(a, b, a + 1, b, b + 1, a + 1);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geometry.setIndex(index);
    const mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ color: this.ink, toneMapped: false, side: THREE.DoubleSide }));
    mesh.userData.unpickable = true;
    const nearest = outer.reduce((best, point) => (point[1] > best[1] ? point : best), outer[0]);
    const middle = outer.reduce((sum, [x]) => sum + x, 0) / outer.length;
    return { mesh, indices, anchor: [middle, nearest[1]] };
  }

  /** Three dots on each cell's top, one for each molecule of the switch, each as large (by its area) as its share of that molecule's largest saved amount in the runs in view. */
  dotsOf(item, sheet, thick) {
    const species = item.amounts.filter((amount) => amount.record);
    if (!species.length) return null;
    const mesh = new THREE.InstancedMesh(new THREE.CircleGeometry(1, 28).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ toneMapped: false, side: THREE.DoubleSide }), sheet.cells.length * species.length);
    mesh.userData.unpickable = true;
    mesh.userData.species = species;
    mesh.renderOrder = 3;
    const colour = new THREE.Color();
    sheet.cells.forEach((_, k) => species.forEach((amount, m) => mesh.setColorAt(k * species.length + m, colour.set(this.colours.molecules?.[m] || "#888888"))));
    return mesh;
  }

  /**
   * The colours the beads are drawn in: what crosses a junction stands out from the cells it crosses between, which are
   * deep on a light page and pale on a dark one, so the beads are white on a light page and the page's dark ground on a
   * dark one (`colours.bead`).
   */
  streamColours() {
    const palette = this.stage?.palette || {};
    const css = this.colours.bead || (palette.dark ? palette.bg || "#0d1b2a" : "#ffffff");
    const crossing = new THREE.Color(css);
    return { ink: this.ink, ground: new THREE.Color(palette.bg || "#eef2f6"), ion: () => crossing, ionCss: () => css, dark: Boolean(palette.dark) };
  }

  /** A time of a run on its map from a share of the map's depth (a press on a map moves the clock to that run's record). */
  timeAtShare(share, run) {
    const at = Math.min(1, Math.max(0, share)), t = run.t;
    let best = 0;
    for (let k = 0; k < t.length; k++) if (this.axisNow.at(t[k]) <= at + 1e-9) best = k;
    return t[best];
  }

  /** Colour the cells and size their dots by the record at the clock; ring the cells whose stated state changed at it; move the maps' cursors and the beads. */
  draw() {
    if (!this.pieces || !this.runs.length) return;
    const rgb = [0, 0, 0], matrix = new THREE.Matrix4(), hidden = new THREE.Matrix4().makeScale(0, 0, 0);
    this.changedNow = [];
    for (const piece of this.pieces.values()) {
      if (piece.refused) continue;
      const { item, sheet, surface, dots, rings, cursor, mapAt, mapDepth, stream, thick } = piece;
      // Each run shows its own record at or before the clock; past its end, its last record (said so: placeTags).
      const index = item.run.indexAt(this.player.time);
      stream?.update(index, true);
      if (cursor) cursor.position.z = mapAt.z0 + this.axisNow.at(item.run.t[index]) * mapDepth;
      // While its record stays the one shown (a change held on the screen), nothing of it is painted again.
      if (piece.shown === index) {
        this.changedNow.push(...(piece.changed || []));
        continue;
      }
      piece.shown = index;
      paint(surface, (k) => this.breaks.colour(item.record.at(index, item.cells.columns[k]), rgb));
      if (sheet.seams) paintSeams(sheet.seams, this.ink);
      if (dots) {
        const species = dots.userData.species, pitch = sheet.pitch;
        sheet.cells.forEach((cell, k) =>
          species.forEach((amount, m) => {
            const share = Math.max(0, amount.record.at(index, item.cells.columns[k])) / this.most[amount.id];
            const radius = Math.max(0.03, Math.sqrt(Math.min(1, share))) * 0.2 * pitch;
            // The three round the cell's middle, a third of a turn apart, on its top.
            const turn = (m / species.length) * 2 * Math.PI - Math.PI / 2, reach = species.length > 1 ? 0.21 * pitch : 0;
            matrix.makeScale(radius, 1, radius).setPosition(cell.centre[0] + Math.cos(turn) * reach, thick + 0.02 * pitch, cell.centre[1] + Math.sin(turn) * reach);
            dots.setMatrixAt(k * species.length + m, matrix);
          })
        );
        dots.instanceMatrix.needsUpdate = true;
      }
      // The cells whose stated state changed at the record shown: ringed, and named on the picture (placeTags).
      const changed = this.changes.filter((change) => change.arm === item.slot.arm && change.record === index);
      for (let k = 0; k < item.cells.count; k++) rings.setMatrixAt(k, hidden);
      for (const change of changed) {
        const cell = sheet.cells[change.cell];
        matrix.makeScale(cell.radius * 1.22, 1, cell.radius * 1.22).setPosition(cell.centre[0], thick + 0.03 * sheet.pitch, cell.centre[1]);
        rings.setMatrixAt(change.cell, matrix);
      }
      rings.instanceMatrix.needsUpdate = true;
      piece.changed = changed.map((change) => ({ change, piece }));
      this.changedNow.push(...piece.changed);
    }
    this.placeMarks();
    this.placeTags();
  }

  /** The chosen and the hovered cell: a ring round the cell and a frame round its column of the map. */
  placeMarks() {
    for (const piece of this.pieces?.values() || []) {
      if (piece.refused) continue;
      const which = this.selected?.arm === piece.item.slot.arm ? this.selected : this.hovered?.arm === piece.item.slot.arm ? this.hovered : null;
      if (!piece.chosen) {
        piece.chosen = new THREE.Mesh(new THREE.RingGeometry(1, 1.16, 48).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: this.ink, toneMapped: false, side: THREE.DoubleSide }));
        piece.chosen.userData.unpickable = true;
        piece.chosen.renderOrder = 7;
        piece.group.add(piece.chosen);
      }
      piece.chosen.visible = Boolean(which);
      if (piece.column) piece.column.visible = Boolean(which);
      if (!which) continue;
      const cell = piece.sheet.cells[which.cell];
      piece.chosen.material.color.copy(which === this.selected ? this.ink : this.soft);
      piece.chosen.scale.setScalar(cell.radius * 1.08);
      piece.chosen.position.set(cell.centre[0], piece.thick + 0.05 * piece.sheet.pitch, cell.centre[1]);
      if (!piece.column) continue;
      const w = piece.mapWidth / piece.item.cells.count;
      piece.column.scale.set(w, 1, piece.mapDepth);
      piece.column.position.set(piece.mapAt.x0 + which.cell * w, 0, piece.mapAt.z0);
    }
  }

  // ------------------------------------------------------------ words on the picture

  /**
   * The words that change with the clock: a run past its record's end says so in its end words; the cells whose stated
   * state changed at the record shown are named (a line's in the row under it kept for that, "cell 6: M to X"; a sheet's
   * of one record and kind together, over their middle, "c3_3, c3_5: M to X"); the chosen cell is named with the
   * driver's state (a line's in the row under it kept for that). Every other name stands where build() put it.
   */
  placeTags() {
    if (!this.active || !this.tags) return;
    const { labels, tags } = this;
    for (const { tag, end } of tags.ended) {
      const early = tag.element.querySelector(".is-early");
      if (early) early.style.visibility = this.player.time > end + 1e-6 ? "visible" : "hidden";
    }
    const pxOf = (piece, x) => piece.row.cellsAt.x + x * this.pxScale * piece.row.block.scale;
    const under = (piece, xPx, yPx, label) => piece.row.block.root.localToWorld(new THREE.Vector3(piece.row.block.xOf(xPx), 0, piece.row.block.unit(yPx + label.height)));
    // Made again only when the changes shown are others (a play draws every frame; the names stay while their record shows).
    const key = (this.changedNow || []).map(({ change }) => `${change.arm}:${change.cell}:${change.record}`).join("|");
    if (key !== tags.changeKey) {
      tags.changeKey = key;
      for (const tag of tags.changes) labels.remove(tag);
      const together = new Map();
      for (const { change, piece } of this.changedNow || []) {
        const at = piece.item.lined ? piece.row.slot.arm : `${piece.row.slot.arm}:${change.from}:${change.to}`;
        if (!together.has(at)) together.set(at, { piece, changes: [] });
        together.get(at).changes.push(change);
      }
      tags.changes = [...together.values()].map(({ piece, changes }) => {
        const cells = changes.map((change) => piece.sheet.cells[change.cell]);
        const x = cells.reduce((sum, cell) => sum + cell.centre[0], 0) / cells.length, z = cells.reduce((sum, cell) => sum + cell.centre[1], 0) / cells.length;
        const lined = piece.item.lined;
        const words = lined ? changes.map((change) => change.words).join("; ") : changes.length === 1 ? changes[0].words : `${changes.map((change) => change.name).join(", ")}: ${changes[0].from} to ${changes[0].to}`;
        const tag = labels.add({ text: words, anchor: new THREE.Vector3(), kind: "tissue-change", priority: 10, lift: 0 });
        tag.boost = 1000;
        if (lined) {
          tag.px = pxOf(piece, x);
          tag.piece = piece;
          tag.anchor.copy(under(piece, tag.px, piece.row.calloutY, tag));
        }
        else {
          // Over the changed cells' middle, on the picture.
          tag.anchor.copy(piece.group.localToWorld(new THREE.Vector3(x, piece.thick, z)));
          tag.lift = -tag.height / 2;
        }
        return tag;
      });
    }
    const piece = this.selected ? this.pieces?.get(this.selected.arm) : null;
    if (!piece?.item) {
      if (tags.chosen) {
        labels.show(tags.chosen, false);
        tags.chosen.hidden = true;
      }
      return;
    }
    const { item, sheet } = piece, k = this.selected.cell, cell = sheet.cells[k];
    const index = item.run.indexAt(this.player.time);
    const state = item.states ? item.states.text(index, item.cells.columns[k]) : null;
    const words = `${item.cells.ids[k]}${state ? ` · ${state}` : ""}`;
    if (!tags.chosen) {
      tags.chosen = labels.add({ text: words, anchor: new THREE.Vector3(), kind: "tissue-state", priority: 10, lift: 0 });
      tags.chosen.boost = 1000;
    }
    const tag = tags.chosen;
    tag.hidden = false;
    labels.setText(tag, words);
    if (item.lined) {
      tag.lift = 0;
      // In the row under the line, beside a change's name standing there.
      let x = pxOf(piece, cell.centre[0]);
      const beside = tags.changes.find((other) => other.piece === piece);
      if (beside && Math.abs(x - beside.px) < (tag.width + beside.width) / 2 + 6) {
        const right = beside.px + (beside.width + tag.width) / 2 + 6, left = beside.px - (beside.width + tag.width) / 2 - 6;
        x = right + tag.width / 2 <= piece.row.block.size.width ? right : left;
      }
      tag.anchor.copy(under(piece, x, piece.row.chosenY, tag));
    } else {
      // On a sheet: over the cell, on the picture.
      tag.lift = -tag.height / 2;
      tag.anchor.copy(piece.group.localToWorld(new THREE.Vector3(cell.centre[0], piece.thick, cell.centre[1])));
    }
  }

  // ------------------------------------------------------------ the lens interface

  get pickRoots() {
    return [this.root];
  }

  activate() {
    const { stage } = this;
    this.active = true;
    stage.scene.add(this.root);
    stage.dress?.({ rich: false });
    this.labels.clear();
    this.labels.calloutFrame = null;
    this.tags = null;
    if (this.runs.length) this.enter();
    stage.invalidate();
  }

  /** Lay the tissues out and frame them, and start the clock unless motion is unwanted or the page is held still. */
  enter() {
    const { stage } = this;
    this.build();
    this.home = this.homeView();
    stage.rig.limits = { minDistance: this.home.distance * 0.15, maxDistance: this.home.distance * 3, minPolar: POLAR, maxPolar: 1.45 };
    stage.rig.setView(this.home);
    this.sized = { width: stage.width, height: stage.height, insets: JSON.stringify(stage.insets || {}) };
    if (!this.autoplayed && !stage.reducedMotion && !stage.rig.instant && this.player.time === this.player.start && !Number.isFinite(this.pendingTime)) this.player.play();
    this.autoplayed = true;
  }

  deactivate() {
    this.active = false;
    this.player.pause();
    this.stage.scene.remove(this.root);
    this.labels.clear();
    this.tags = null;
  }

  /** The room changed (a panel opened, the window turned): laid out again for it, and framed. */
  roomChanged() {
    if (!this.active || !this.runs.length || !this.home) return;
    // A window that turned narrow keeps the insets the page set while it was wide (src/ui/viewer.js sets them in renderPanel,
    // which a change of width does not call): on a narrow window the page leaves no room at the sides, so none is kept.
    const insets = this.stage.insets || {};
    if (this.stage.width < 760 && (insets.left || insets.right)) this.stage.setInsets({ bottom: insets.bottom || 0 });
    this.sized = { width: this.stage.width, height: this.stage.height, insets: JSON.stringify(this.stage.insets || {}) };
    const { rig } = this.stage;
    this.build();
    const next = this.homeView();
    this.home = next;
    rig.limits = { ...rig.limits, minDistance: next.distance * 0.15, maxDistance: next.distance * 3 };
    rig.setView(next);
    this.draw();
  }

  /**
   * The camera that frames the layout in the room the page leaves the picture, from straight above: found by projecting
   * the layout's corners through the stage's own camera (its view offset keeps the cards' room) and moving and pulling
   * back until they fill the room.
   */
  homeView() {
    const { stage } = this;
    const camera = stage.camera, room = this.room(), box = this.box;
    const saved = { position: camera.position.clone(), quaternion: camera.quaternion.clone() };
    const corners = [];
    for (const x of [box.x0, box.x1]) for (const z of [box.z0, box.z1]) corners.push(new THREE.Vector3(x, 0, z));
    const left = room.left + room.margin, right = left + room.width, top = room.top, bottom = top + room.height;
    const direction = new THREE.Vector3(0, Math.cos(POLAR), Math.sin(POLAR));
    const target = new THREE.Vector3((box.x0 + box.x1) / 2, 0, (box.z0 + box.z1) / 2);
    const half = Math.tan((camera.fov * Math.PI) / 360);
    let distance = Math.max(box.x1 - box.x0, box.z1 - box.z0) / (2 * half);
    const point = new THREE.Vector3(), rightWay = new THREE.Vector3(), upWay = new THREE.Vector3();
    for (let round = 0; round < 10; round++) {
      camera.position.copy(target).addScaledVector(direction, distance);
      camera.lookAt(target);
      camera.updateMatrixWorld();
      let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
      for (const corner of corners) {
        stage.project(point.copy(corner), point);
        x0 = Math.min(x0, point.x);
        x1 = Math.max(x1, point.x);
        y0 = Math.min(y0, point.y);
        y1 = Math.max(y1, point.y);
      }
      // Moved so that the layout's middle stands in the room's, and pulled back or in to the scale it was laid out at.
      const perPixel = (2 * distance * half) / stage.height;
      rightWay.setFromMatrixColumn(camera.matrixWorld, 0);
      upWay.setFromMatrixColumn(camera.matrixWorld, 1);
      target.addScaledVector(rightWay, ((x0 + x1) / 2 - (left + right) / 2) * perPixel);
      target.addScaledVector(upWay, -((y0 + y1) / 2 - (top + bottom) / 2) * perPixel);
      distance *= (x1 - x0) / Math.max(1, (box.x1 - box.x0) * this.pxScale);
    }
    camera.position.copy(saved.position);
    camera.quaternion.copy(saved.quaternion);
    camera.updateMatrixWorld();
    return { target, distance, azimuth: 0, polar: POLAR };
  }

  setSelection(id) {
    this.panel = id || null;
    const cell = this.cellOf(id);
    this.selected = cell;
    // A press on a map moves the clock to the record pressed (picked said where, just before).
    if (cell && this.pressedAt?.id === id) {
      this.player.pause();
      this.player.seek(this.pressedAt.time);
    }
    this.pressedAt = null;
    this.draw();
    this.stage?.invalidate();
  }

  /** Where a press on the picture landed (src/ui/viewer.js, before it chooses what was hit): on a map, the record pressed. */
  picked(hit) {
    const at = hit?.object?.userData.recordAt;
    this.pressedAt = at && hit.id ? { id: hit.id, time: at(hit) } : null;
  }

  setHover(id) {
    const next = this.cellOf(id);
    if (JSON.stringify(next) === JSON.stringify(this.hovered)) return;
    this.hovered = next;
    this.placeMarks();
    this.stage?.invalidate();
  }

  setIsolate() {}

  /** A cell chosen from the list or the address: the camera stays where it frames every tissue; the cell is ringed and named there. */
  focus() {}

  /** Move the clock; before the runs are in, the time is kept for when they are (the address's `time=`). */
  seek(seconds) {
    if (!Number.isFinite(seconds)) return;
    if (this.runs.length) this.player.seek(seconds);
    else this.pendingTime = seconds;
  }

  update(dt, time, real = dt) {
    if (!this.active) return false;
    // The window changed size (turned, or made narrow): laid out and framed again, as when the page's cards change the room.
    const { width, height } = this.stage;
    if (this.sized && (this.sized.width !== width || this.sized.height !== height)) this.roomChanged();
    this.sized = { width, height };
    const was = this.player.playing;
    const playing = this.player.tick(real);
    let moving = false;
    // The beads keep the clock: as much of the run passes for them as for the playhead.
    if (was && this.pieces) for (const piece of this.pieces.values()) if (piece.stream) moving = piece.stream.tick(real) || moving;
    return playing || moving;
  }

  /** A cell named by its id, or null. */
  cellOf(id) {
    if (typeof id !== "string" || !id.startsWith(CELL_ID)) return null;
    const [arm, cell] = [id.slice(CELL_ID.length, id.lastIndexOf(":")), Number(id.slice(id.lastIndexOf(":") + 1))];
    const item = this.runs.find((run) => run.slot.arm === arm);
    return item && Number.isInteger(cell) && cell >= 0 && cell < item.cells.count ? { arm, cell } : null;
  }

  has(id) {
    if (typeof id !== "string") return false;
    if (id.startsWith(RUN)) return this.runs.some((item) => item.run.id === id.slice(RUN.length));
    return Boolean(this.cellOf(id));
  }

  /** The list: each run, then its cells. */
  sections() {
    return this.runs.map((item) => ({
      label: `${item.group.line.short}: ${item.slot.label}`,
      entities: [{ id: RUN + item.run.id, label: `The run at ${item.slot.label}` }, ...item.cells.ids.map((name, k) => ({ id: `${CELL_ID}${item.slot.arm}:${k}`, label: `${name} at ${item.slot.short}`, keywords: item.group.line.tumor?.cells?.includes(name) ? "tumor" : "" }))],
    }));
  }

  entities() {
    return this.sections().flatMap((section) => section.entities);
  }

  describe(id) {
    if (typeof id !== "string") return null;
    if (id.startsWith(RUN)) {
      const item = this.runs.find((run) => run.run.id === id.slice(RUN.length));
      return item ? { ...this.catalogue.describe(id, item.run), eyebrow: item.group.line.entry.label } : null;
    }
    const cell = this.cellOf(id);
    if (!cell) return null;
    const item = this.runs.find((run) => run.slot.arm === cell.arm);
    const column = item.cells.columns[cell.cell], name = item.cells.ids[cell.cell];
    const index = item.run.indexAt(this.player.time);
    const state = item.states ? item.states.text(index, column) : null;
    const line = item.group.line;
    const tumor = line.tumor?.cells?.includes(name);
    const label = item.record.label;
    const at = clock(item.run.t[index], { precise: true });
    const changes = this.changes.filter((change) => change.arm === cell.arm && change.cell === cell.cell);
    const amounts = item.amounts.filter((amount) => amount.record).map((amount) => [`${amount.label} at ${at} (${amount.stated ? "as the driver states it" : "saved"})`, reading(amount.record, amount.record.at(index, column)) || "no value"]);
    return {
      id,
      label: `${name}, at ${item.slot.label}`,
      eyebrow: line.entry.label,
      kind: "cell",
      plain: `One cell of the tissue in the run at ${item.slot.label}. The chart shows its ${lower(label)} at every saved record, as the experiment's driver states it beside the run; the line through it is the clock.`,
      note: `Every point is a saved record, and nothing is interpolated between them. The state is the driver's own (${item.record.stated?.file || "its file"}), never read from the colour.`,
      chips: [{ label: item.slot.label, title: "The run this cell is shown in." }, ...(tumor ? [{ label: "Tumor", title: line.tumor.source || "" }] : [])],
      facts: [
        ["Run", item.slot.arm],
        [`${label} at ${at}`, reading(item.record, item.record.at(index, column)) || "no value"],
        ...(state ? [["State there, as the driver states it", state]] : []),
        ...amounts,
        ...(item.slot.end ? [[line.endsLabel, item.slot.end]] : []),
      ],
      chart: {
        run: item.run,
        record: item.record,
        index: column,
        player: this.player,
        title: label,
        judged: null,
        levels: item.record.marks || [],
        events: changes.map((change) => ({ time: change.time, label: change.words })),
        extra: item.states ? (step) => `state ${item.states.text(step, column)}` : null,
      },
      sections: [
        changes.length
          ? { title: "When its stated state changed", items: changes.map((change) => ({ label: `At ${clock(change.time)}`, detail: `${change.from} to ${change.to}` })) }
          : { title: "When its stated state changed", items: [{ label: "Never in this run", detail: state ? `${state} throughout` : "" }] },
      ],
      related: [],
      sources: line.sources,
    };
  }

  chrome() {
    const line = this.line;
    const status = this.error ? `The tissue could not be shown: ${this.error}` : this.loading ? "Loading the tissue's runs…" : null;
    const revision = this.runs[0]?.run.info.revision;
    const chrome = {
      quiet: true,
      status,
      // The record's first line of the part (its standing: development work, not judged) heads the stamp, so that it is in sight beside the pictures' captions.
      stamp: [line?.says?.[0]?.replace(/\.$/, ""), line?.entry.short || line?.entry.label, revision ? `engine ${revision.slice(0, 8)}` : null].filter(Boolean).join(" · "),
      timeline: this.runs.length ? { player: this.player, eventWord: "change", stops: true } : null,
      card: line
        ? {
            heading: line.entry.label,
            stats: [],
            text: null,
            own: () => this.cardParts(),
            choices: this.runs.length
              ? [
                  // The arms in view: those the entries put in front (the picture's choice), or every arm, fetched as it comes into view.
                  ...(this.someLeftOut() ? [{ key: "arms", label: "In view", options: [["front", `${this.groups.reduce((sum, group) => sum + (group.front?.length || group.line.runs.length), 0)} arms (the picture's choice)`], ["all", `All ${this.groups.reduce((sum, group) => sum + group.line.runs.length, 0)}`]], active: this.everyArm ? "all" : "front", set: (value) => this.setEveryArm(value === "all") }] : []),
                  { key: "time-scale", label: "Time down the maps", options: TIME_SCALES, active: this.scale, set: (value) => this.setScale(value) },
                ]
              : [],
            sources: line.sources.map((source) => ({ name: source.path, url: this.model.sourceUrl?.(source) || null, holds: source.where, licence: source.revision ? `at ${source.revision.slice(0, 8)}` : "" })),
          }
        : { heading: "The tissue", stats: [], text: status || "", sources: [] },
      legend: { title: "Shown", items: [] },
    };
    if (this.runs.length) {
      const record = this.runs[0].record;
      const unit = unitSign(record.unit);
      const span = this.breaks.high - this.breaks.low, at = (value) => (value - this.breaks.low) / span;
      chrome.legend.scale = {
        label: record.label,
        unit,
        gradient: this.breaks.css(),
        ticks: [this.breaks.low, 0, this.breaks.high].filter((value, k, all) => all.indexOf(value) === k && value >= this.breaks.low && value <= this.breaks.high).map((value) => ({ at: at(value), text: number(value, 0) })),
        marks: record.marks.map((mark) => ({ at: at(mark.value), text: `${number(mark.value, 1)} ${unit}: ${mark.label}` })),
        said: `The colour of a cell is the experiment's own quantity, stated by its driver beside each run (${record.stated?.file || "its file"}) and copied as stated: not a field of the engine. The scale breaks at the criterion's thresholds. The criterion's own words are in the card.`,
      };
      const species = this.runs[0].amounts.filter((amount) => amount.record);
      const stream = [...(this.pieces?.values() || [])].find((piece) => piece.stream)?.stream;
      chrome.legend.keys = [
        ...(species.length
          ? [
              {
                key: "tissue-bars",
                chips: species.map((amount, m) => ({ colour: this.colours.molecules?.[m], label: amount.label })),
                text: species[0].stated
                  ? `Three dots in a cell: its concentrations at the record shown, as the driver states them beside the run, each as large (by its area) as its share of its largest in the runs in view (${species.map((amount) => `${amount.label} ${number(this.most[amount.id], 1)} ${unitSign(amount.record.unit)}`).join(", ")})`
                  : `Three dots in a cell: its saved amounts at the record shown, each as large (by its area) as its share of its largest in these runs (${species.map((amount) => `${amount.label} ${number(this.most[amount.id] * 1000, 1)} amol`).join(", ")})`,
              },
            ]
          : []),
        // A bead: what crossed a junction, by the species' own name (the summary's), in the beads' colour.
        ...(stream
          ? [
              { key: "ions", chips: [{ colour: this.streamColours().ionCss(), label: speciesWords(line).find((item) => item.id === stream.lanes.find((lane) => lane.species)?.species)?.label || "what crosses" }], text: "A bead on a junction: what its route carried there, as the run saved it, moving the way the record's sign gives" },
              ...stream.keys().filter((key) => key.key !== "ions"),
            ]
          : [{ key: "unplaced", text: "No run in view saved what its junctions carried: no beads" }]),
        { key: "tissue-ring", text: `A ring and a name over a cell: its stated state changed at the record shown (the driver's words)${this.player.speed === FOLLOW ? `, held ${DWELL} s` : ""}` },
        ...(line.tumor ? [{ key: "tissue-bracket", text: `The outline: ${lower(line.tumor.label)} (${line.tumor.source})` }] : []),
        ...(this.blocks?.some((block) => block.maps) ? [{ key: "tissue-line", text: `${this.blocks.every((block) => block.maps) ? "Beside each tissue" : "Beside each line"} its whole run as a map: the same cells across, time running away from the tissue; the bar across it is the clock` }] : []),
        ...(this.bracket ? [{ key: "tissue-threshold", text: `The dashed line: ${lower(this.line.entry.tissue?.bracket?.says || "")}` }] : []),
        ...(line.refused.length ? [{ key: "tissue-refused", text: "A dashed place: a pick an engine check refused, with no run to show" }] : []),
      ];
      chrome.legend.note = { text: `${this.player.speed === FOLLOW ? `The clock plays the stated changes: each is held ${DWELL} s, the time between two changes passes in a second or less; the timeline's marks are the changes, each named. ` : ""}${this.axisNow?.words || ""}` };
      chrome.legend.folded = true;
    }
    return chrome;
  }

  /**
   * What the card says beyond the experiment's heading: the way to the networks; the example's other parts, one whose
   * entry gives a caption under its caption (the sheet, from the line); the plain lines and the record's own lines; the
   * changes; the criterion; then each group's picks in their places.
   */
  cardParts() {
    const line = this.line;
    if (!line) return [];
    const whole = this.catalogue.experiments.get(line.entry.part_of);
    const others = typeof this.open === "function" ? partsOf(this.model.raw.replays, line.entry.part_of).filter((part) => part.id !== line.id) : [];
    const door = (part) => h("button", { class: "tissue-back tissue-sibling", type: "button", dataset: { part: part.id }, onclick: () => this.open(part.id) }, part.short || part.label);
    const groups = this.groups?.length ? this.groups : [{ id: line.id, line, role: "main", front: line.entry.tissue?.front }];
    return [
      // The way to the example's networks, at the card's head: on a phone the tab's list is a select whose chosen option is the example already.
      typeof this.back === "function" && whole ? h("button", { class: "tissue-back", type: "button", onclick: () => this.back() }, "The example's networks and sweeps") : null,
      // The example's other parts, each its own view here: a part with a caption of its own stands under it, in full.
      ...others.map((part) => (part.tissue?.caption ? h("div", { class: "tissue-sibling-block", dataset: { part: part.id } }, h("p", { class: "card-text" }, part.tissue.caption), door(part)) : door(part))),
      h("p", { class: "card-text" }, line.entry.plain),
      h("ul", { class: "tissue-says" }, line.says.map((said) => h("li", {}, said))),
      // Which arms stand in view, and why, while only some do (the picture's choice).
      ...(!this.everyArm ? groups.map((group) => (group.role === "beside" ? group.frontSays : group.line.entry.tissue?.front_says)).filter(Boolean).map((said) => h("p", { class: "card-text tissue-front" }, said)) : []),
      // The changes of the runs in view, each a press away: the timeline's marks, in a list.
      this.marks.length
        ? h(
            "details",
            { class: "tissue-changes" },
            h("summary", {}, `Stated changes · ${this.changes.length}`),
            h("ul", {}, this.marks.map((mark) => h("li", {}, h("button", { class: "link-button", type: "button", dataset: { time: String(mark.time) }, onclick: () => (this.player.pause(), this.player.seek(mark.time)) }, mark.label))))
          )
        : null,
      // The criterion in its own words, with its source, as the driver's file gives them.
      ...(this.runs[0]?.record.criterion ? [h("details", { class: "tissue-criterion" }, h("summary", {}, "The criterion, in its own words"), h("p", { class: "card-text" }, `“${this.runs[0].record.criterion.words}”`), h("p", { class: "card-text tissue-criterion-source" }, `Its source, as the file gives it: ${this.runs[0].record.criterion.source}`))] : []),
      ...groups.map((group) =>
        h(
          "div",
          { class: "tissue-slots", role: "group", "aria-label": group.role === "main" ? "The picks, in the order of D" : group.caption, dataset: { group: group.id } },
          h("span", { class: "seg-label" }, group.role === "main" ? `Picks · ${group.line.slots.length}` : `${group.caption} · ${group.line.slots.length}`),
          ...group.line.slots.map((slot) =>
            h(
              "div",
              { class: `tissue-slot${slot.kind === "refused" ? " is-refused" : ""}`, dataset: { arm: slot.arm } },
              h("b", {}, [slot.label, where(slot, null)].filter(Boolean).join(" · ")),
              h("span", {}, slot.kind === "refused" ? group.line.refusedWords : slot.end || ""),
              slot.kind === "run" && this.runs.some((item) => item.slot === slot) ? h("button", { class: "tissue-open", type: "button", onclick: () => this.onShown?.(RUN + slot.id) }, "Run details") : null
            )
          ),
          h("p", { class: "card-text tissue-ends-said" }, group.line.entry.tissue?.ends_says || `${group.line.endsLabel}.`)
        )
      ),
    ].filter(Boolean);
  }

  setScale(value) {
    if (!TIME_SCALES.some(([id]) => id === value) || value === this.scale) return;
    this.scale = value;
    this.build();
    this.onChrome?.();
    this.stage?.invalidate();
  }

  applyPalette() {
    this.colours = readTissueColours(this.stage?.host);
    if (this.breaks) this.breaks.setColours(this.colours);
    if (this.runs.length) this.build();
    if (this.active) this.onChrome?.();
    this.stage?.invalidate();
  }

  dispose() {
    this.dropPieces();
    disposeTree(this.root);
  }
}

/** A slot's place against the threshold as the summary states it ("x2/4"), with what x2 is where the entry says it; none for D = 0's "0". */
function where(slot, placeSays) {
  return slot.where && /x2/.test(slot.where) ? `${slot.where}${placeSays ? `, ${placeSays}` : ""}` : null;
}

/** A part's species by name, as its run folder's summary states them (`species`: id to name), in their order. */
function speciesWords(line) {
  const said = line?.species;
  return said && typeof said === "object" ? Object.entries(said).map(([id, label]) => ({ id, label })) : [];
}

/** Whether a run's cells stand on one line (a tissue line), not over a plane (a sheet): their polygons' middles share one y. */
function isLine(run) {
  const { vertices = [], faces = [] } = run.sets.get("cell")?.geometry || {};
  const middles = faces.map((face) => face.reduce((sum, index) => sum + vertices[index][1], 0) / face.length);
  const xs = vertices.map(([x]) => x), span = Math.max(...xs) - Math.min(...xs) || 1;
  return middles.length > 1 && middles.every((y) => Math.abs(y - middles[0]) <= 1e-6 * span);
}

/** A stated quantity's own label, to its first clause: "miR200 in each cell, in µM; …" is "miR200". */
function headOf(label) {
  return String(label || "").split(/ in each cell|[;,]/)[0].trim() || String(label || "");
}

/** Whether a saved total never changes in the run (a run with no coupling carries nothing). */
function allStill(run, record) {
  for (let k = 1; k < run.count; k++) for (let e = 0; e < record.width; e++) if (record.at(k, e) !== record.at(0, e)) return false;
  return true;
}

/** The cells of a run as its view places them along the line: x from the first cell's left edge, each radius, and the record's column for each. */
export function cellsOf(run) {
  const set = run.sets.get("cell");
  const ids = (set?.ids || []).filter((id) => id !== null);
  const geometry = set?.geometry;
  const spheres = geometry?.kind === "spheres" && Array.isArray(geometry.centres) && geometry.centres.length === ids.length;
  const radius = ids.map((_, k) => (spheres ? Number(Array.isArray(geometry.radius) ? geometry.radius[k] : geometry.radius) || PITCH / 2 : PITCH / 2));
  const along = ids.map((_, k) => (spheres ? Number(geometry.centres[k][0]) : k * PITCH));
  const start = Math.min(...along.map((x, k) => x - radius[k]));
  const x = along.map((value) => value - start);
  const width = Math.max(...x.map((value, k) => value + radius[k]));
  const columns = ids.map((_, k) => k); // the record's columns follow the set's order (src/replay/run.js)
  return {
    ids,
    count: ids.length,
    x,
    radius,
    width,
    columns,
    /** The cell whose column holds a place along the line, or null. */
    columnAt(offset) {
      for (let k = 0; k < ids.length; k++) if (offset >= x[k] - radius[k] && offset < x[k] + radius[k]) return k;
      return null;
    },
  };
}

/** The seams between joined cells, in the ink's tone: every junction of these runs is drawn alike. */
function paintSeams(seams, ink) {
  const colour = seams.geometry.attributes.color;
  for (let k = 0; k < seams.quads.length * 4; k++) colour.array.set([ink.r, ink.g, ink.b, 0.35], k * 4);
  colour.needsUpdate = true;
}

/** A short channel across the gap between each pair of joined cells' rims: the junction, at the middle of the cells' thickness. */
function channelMesh(run, sheet, thick, ink) {
  const junctions = run.sets.get("junction");
  if (junctions?.geometry?.kind !== "links" || junctions.geometry.between !== "cell") return null;
  const ends = junctions.geometry.ends;
  const mesh = new THREE.InstancedMesh(new THREE.CylinderGeometry(1, 1, 1, 14).rotateZ(Math.PI / 2), new THREE.MeshStandardMaterial({ color: ink, roughness: 0.6, metalness: 0, transparent: true, opacity: 0.6, toneMapped: false }), ends.length);
  const matrix = new THREE.Matrix4(), quaternion = new THREE.Quaternion(), along = new THREE.Vector3(1, 0, 0);
  ends.forEach(([a, b], k) => {
    const one = sheet.cells[a], other = sheet.cells[b];
    const dx = other.centre[0] - one.centre[0], dz = other.centre[1] - one.centre[1], apart = Math.hypot(dx, dz) || 1;
    // From well inside one cell's rim to well inside the other's: the channel is seen between the two.
    const length = Math.max(apart - (one.radius + other.radius) * 0.72, 0.1 * sheet.pitch);
    quaternion.setFromUnitVectors(along, new THREE.Vector3(dx / apart, 0, dz / apart));
    matrix.compose(new THREE.Vector3((one.centre[0] + other.centre[0]) / 2, thick * 0.5, (one.centre[1] + other.centre[1]) / 2), quaternion, new THREE.Vector3(length, 0.09 * sheet.pitch, 0.09 * sheet.pitch));
    mesh.setMatrixAt(k, matrix);
  });
  mesh.userData.unpickable = true;
  return mesh;
}

/** One flat ring for each cell, shown where its stated state changed at the record shown. */
function ringMesh(count, hex) {
  const mesh = new THREE.InstancedMesh(new THREE.RingGeometry(0.92, 1.1, 48).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: new THREE.Color(hex), toneMapped: false, side: THREE.DoubleSide }), count);
  const hidden = new THREE.Matrix4().makeScale(0, 0, 0);
  for (let k = 0; k < count; k++) mesh.setMatrixAt(k, hidden);
  mesh.userData.unpickable = true;
  mesh.renderOrder = 7;
  return mesh;
}

/** The whole run as a flat map on the ground: a band for each cell and each saved record, from its time to the next, in the colour of its value. */
function mapMesh(item, x0, z0, width, depth, bandsNow, breaks) {
  const { cells, record } = item;
  const count = cells.count * bandsNow.length;
  const positions = new Float32Array(count * 18), colours = new Float32Array(count * 18);
  const colour = new THREE.Color(), rgb = [0, 0, 0], w = width / cells.count;
  let v = 0;
  for (let k = 0; k < cells.count; k++) {
    const xa = x0 + k * w, xb = xa + w;
    for (const band of bandsNow) {
      const za = z0 + band.from * depth, zb = z0 + band.to * depth;
      breaks.colour(record.at(band.k, cells.columns[k]), rgb);
      colour.setRGB(rgb[0], rgb[1], rgb[2], THREE.SRGBColorSpace);
      for (const [x, z] of [[xa, za], [xa, zb], [xb, zb], [xa, za], [xb, zb], [xb, za]]) {
        positions.set([x, 0.02, z], v * 3);
        colours.set([colour.r, colour.g, colour.b], v * 3);
        v++;
      }
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colours, 3));
  geometry.computeBoundingSphere();
  const mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ vertexColors: true, toneMapped: false, side: THREE.DoubleSide }));
  mesh.name = "space-time";
  return mesh;
}

function lineLoop(points, colour) {
  const geometry = new THREE.BufferGeometry().setFromPoints(points.map(([x, y, z]) => new THREE.Vector3(x, y, z)));
  return new THREE.LineLoop(geometry, new THREE.LineBasicMaterial({ color: colour, toneMapped: false }));
}

/** A rectangle's edges on the ground, x0..x1 by z0..z1, a little above it. */
function rectLines(x0, x1, z0, z1, colour, y = 0.03) {
  return lineLoop([[x0, y, z0], [x1, y, z0], [x1, y, z1], [x0, y, z1]], colour);
}

/** A dashed line on the ground from one point to another. */
function dashedLine(from, to, colour, dashSize = 3, gapSize = 2) {
  const geometry = new THREE.BufferGeometry().setFromPoints([from, to]);
  const line = new THREE.LineSegments(geometry, new THREE.LineDashedMaterial({ color: colour, dashSize, gapSize, toneMapped: false }));
  line.computeLineDistances();
  return line;
}

function dashedRect(x0, x1, z0, z1, colour) {
  const line = rectLines(x0, x1, z0, z1, colour);
  line.material = new THREE.LineDashedMaterial({ color: colour, dashSize: 1.6, gapSize: 1.2, toneMapped: false });
  line.computeLineDistances();
  return line;
}

/** The convex hull of points in a plane (Andrew's monotone chain). */
function convexHull(points) {
  const sorted = [...points].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lowerHull = [], upperHull = [];
  for (const point of sorted) {
    while (lowerHull.length >= 2 && cross(lowerHull[lowerHull.length - 2], lowerHull[lowerHull.length - 1], point) <= 0) lowerHull.pop();
    lowerHull.push(point);
  }
  for (const point of [...sorted].reverse()) {
    while (upperHull.length >= 2 && cross(upperHull[upperHull.length - 2], upperHull[upperHull.length - 1], point) <= 0) upperHull.pop();
    upperHull.push(point);
  }
  return [...lowerHull.slice(0, -1), ...upperHull.slice(0, -1)];
}

/** A convex ring pushed out by `distance` along each corner's mean outward normal. */
function offsetRing(ring, distance) {
  const n = ring.length;
  // The hull runs anticlockwise in (x, y): an edge's outward normal is its direction turned a quarter clockwise.
  return ring.map((point, k) => {
    const before = ring[(k + n - 1) % n], after = ring[(k + 1) % n];
    const normal = (a, b) => {
      const dx = b[0] - a[0], dy = b[1] - a[1], length = Math.hypot(dx, dy) || 1;
      return [dy / length, -dx / length];
    };
    const [ax, ay] = normal(before, point), [bx, by] = normal(point, after);
    let nx = ax + bx, ny = ay + by;
    const length = Math.hypot(nx, ny) || 1;
    nx /= length;
    ny /= length;
    const cos = Math.max(0.3, nx * ax + ny * ay);
    return [point[0] + (nx * distance) / cos, point[1] + (ny * distance) / cos];
  });
}
