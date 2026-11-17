// The gap-junction example's tissue line, in the Experiments tab's place (src/ui/viewer.js, showPart): a line of
// cells run on the engine at several strengths of coupling, all under one clock. Each run is its line of cells,
// as spheres where its view prescribes them, above its own space–time picture: the same cells across, each
// saved record a band down the picture from its time to the next, coloured by the quantity the experiment's
// driver states beside the run, on a scale broken at its criterion's own thresholds (src/replay/tissue_line.js).
// A cursor across every picture is the clock's time, and the spheres above show that record. The picks an
// engine check refused stand in their place in the parameter's order, named, with nothing drawn in them.
//
// It shows what the runs saved and what the driver states: nothing is interpolated, no state is read from a
// colour, no count and no front is worked out. A cell's state is the driver's, in the driver's word.
//
// On a wide window the runs stand side by side; on a tall one, one above the other. The time scale (logarithmic,
// where it opens, or even) is the picture's choice, said under the pictures and in the legend.

import * as THREE from "../three.js";
import { disposeTree } from "../core/stage.js";
import { loadRun } from "../replay/source.js";
import { Player } from "../replay/player.js";
import { Catalogue, RUN } from "../replay/catalogue.js";
import { clock, duration, number, reading, unitSign } from "../replay/format.js";
import { lineOf, oneClock, Breaks, rangeOf, timeAxis, bands, TIME_SCALES, PART } from "../replay/tissue_line.js";
import { readTissueColours } from "../ui/tissue_styles.js";
import { mountPartStyles } from "../ui/tissue_part.js";
import { h } from "../ui/dom.js";

export const CELL_ID = "tissue:"; // a cell of a run: `tissue:<arm>:<cell index>`
const PITCH = 10; // the scene's unit is the view's micrometre; where a view gives no geometry, cells stand 10 apart
const SIDE = Math.PI / 2;
const lower = (text) => (text ? text.charAt(0).toLowerCase() + text.slice(1) : "");

/** The lens for a part of an example, with its styles mounted once (the page's tokens and the viewer's shadow rules). */
export function makeTissueLens(stage, model, labels, partId, { root = null, document = globalThis.document, back = null } = {}) {
  mountPartStyles(root, document);
  return new TissueLineLens(stage, model, labels, partId, { back });
}

export class TissueLineLens {
  constructor(stage, model, labels, partId, { back = null } = {}) {
    this.id = "experiments";
    this.back = back; // gives the tab back to the example (src/ui/viewer.js, showExample), from the card's own button
    this.partId = partId;
    this.stage = stage;
    this.model = model;
    this.labels = labels;
    this.catalogue = new Catalogue(model.raw.replays);
    this.line = lineOf(model.raw.replays, partId);
    this.player = new Player();
    this.root = new THREE.Group();
    this.root.name = "tissue-line";
    this.wantsLeftRoom = true; // framed in the room the cards on the left leave it (src/ui/viewer.js, renderPanel)
    this.active = false;
    this.loading = true;
    this.error = null;
    this.runs = []; // [{ slot, run, record, states }]
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
    this.ready = this.load();
  }

  // ------------------------------------------------------------ the runs

  async load() {
    try {
      if (!this.line) throw new Error(`the catalogue has no tissue line called ${this.partId}`);
      const opened = await Promise.all(this.line.runs.map((slot) => loadRun(slot.row)));
      oneClock(opened); // the runs share their saved times, or are not shown together
      const wanted = this.line.entry.opens?.record;
      const ids = Array.isArray(wanted) ? wanted : wanted ? [wanted] : [];
      this.runs = this.line.runs.map((slot, k) => {
        const run = opened[k];
        const record = ids.map((id) => run.records.get(id)).find((item) => item && item.set === "cell" && item.marks?.length);
        if (!record) throw new Error(`the run ${slot.arm} has no stated quantity with a criterion to colour its cells by`);
        return { slot, run, record, states: record.states ? run.records.get(record.states) || null : null, cells: cellsOf(run) };
      });
      this.clockRun = this.runs[0].run;
      const { low, high } = rangeOf(this.runs.map((item) => item.record));
      this.breaks = new Breaks(this.runs[0].record.marks, low, high, this.colours);
      this.player.load(this.clockRun);
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

  /** The axis the pictures are drawn on now. */
  axis() {
    const t = this.clockRun.t;
    return timeAxis(this.clockRun.start, this.clockRun.end, { scale: this.scale, step: t.length > 1 ? t[1] - t[0] : null });
  }

  // ------------------------------------------------------------ layout and drawing

  /** Where each slot stands, in the scene's units, for the room the picture has: side by side where it is wide, one above the other where it is tall. */
  layout() {
    const { stage } = this;
    const room = this.room();
    const aspect = room.width / Math.max(1, room.height);
    const slots = this.line.slots;
    const lineWidth = 25 * PITCH;
    const width = Math.max(...this.runs.map((item) => item.cells.width), lineWidth);
    // Side by side where the room is wide, one above the other where it is tall (a phone, or a wide window with a panel open).
    const columns = aspect >= 1;
    const placed = [];
    if (columns) {
      const refusedWidth = 9 * PITCH, gap = 3.6 * PITCH, left = 6 * PITCH, top = 3.4 * PITCH, bottom = 3 * PITCH, sphere = PITCH, under = 0.6 * PITCH;
      const total = slots.reduce((sum, slot) => sum + (slot.kind === "run" ? width : refusedWidth), 0) + gap * (slots.length - 1) + left;
      const picture = Math.min(110 * PITCH, Math.max(14 * PITCH, total / aspect - top - sphere - under - bottom));
      let x = left;
      for (const slot of slots) {
        const w = slot.kind === "run" ? width : refusedWidth;
        placed.push({ slot, x0: x, x1: x + w, lineY: -top - sphere / 2, top: -top - sphere - under, bottom: -top - sphere - under - picture, ticks: x === left });
        x += w + gap;
      }
      this.box = { x0: 0, x1: total, y0: -(top + sphere + under + picture + bottom), y1: 0 };
    } else {
      const head = 3.4 * PITCH, sphere = PITCH, under = 0.5 * PITCH, after = 1.4 * PITCH, refused = 2.2 * PITCH, left = 3.4 * PITCH, right = 0.4 * PITCH;
      const runCount = slots.filter((slot) => slot.kind === "run").length;
      const total = left + width + right;
      const fixed = runCount * (head + sphere + under + after) + (slots.length - runCount) * (refused + after) - after;
      const picture = Math.min(60 * PITCH, Math.max(5 * PITCH, (total / aspect - fixed) / Math.max(1, runCount)));
      let y = 0;
      for (const slot of slots) {
        if (slot.kind === "run") {
          placed.push({ slot, x0: left, x1: left + width, lineY: y - head - sphere / 2, top: y - head - sphere - under, bottom: y - head - sphere - under - picture, ticks: true });
          y -= head + sphere + under + picture + after;
        } else {
          placed.push({ slot, x0: left, x1: left + width, lineY: y - refused / 2, top: y, bottom: y - refused, ticks: false });
          y -= refused + after;
        }
      }
      this.box = { x0: 0, x1: total, y0: y + after, y1: 0 };
    }
    this.columns = columns;
    this.places = placed;
    return placed;
  }

  /** The pixels the picture has: the stage less the cards on the left, a panel or chart on the right, the bar above and the timeline below. */
  room() {
    const { stage } = this;
    const narrow = stage.width < 760;
    // The page leaves room at the left and the right only on a wide window (src/ui/viewer.js, renderPanel); insets kept from
    // before the window turned narrow are not this window's.
    const { right = 0, bottom = 0 } = stage.insets || {}, left = narrow ? 0 : stage.insets?.left || 0;
    const top = narrow ? 112 : 64, foot = narrow ? 176 : 100;
    return { width: Math.max(120, stage.width - left - (narrow ? 0 : right) - (narrow ? 0 : 24)), height: Math.max(120, stage.height - top - foot - bottom), top, foot, left, right, bottom };
  }

  build() {
    disposeTree(this.root);
    this.root.clear();
    if (!this.runs.length) return;
    const places = this.layout();
    this.axisNow = this.axis();
    const bandsNow = (this.bandsNow = bands(Array.from(this.clockRun.t), this.axisNow));
    const palette = this.stage?.palette || {};
    this.ink.set(palette.fg || "#12283a");
    this.soft.set(palette.muted || "#566878");
    const frameColour = new THREE.Color(this.colours.frame);
    this.pieces = new Map(); // arm -> { spheres, picture, cursor, place, item }
    const sphereGeometry = new THREE.SphereGeometry(1, 28, 18);
    for (const place of places) {
      const { slot } = place;
      if (slot.kind === "refused") {
        // A pick an engine check refused: a named empty place, dashed, with nothing drawn in it.
        const outline = dashedBox(place.x0, place.x1, place.top - (this.columns ? 0 : 0.2 * PITCH), place.bottom + (this.columns ? 0 : 0.2 * PITCH), frameColour);
        outline.userData.unpickable = true;
        this.root.add(outline);
        continue;
      }
      const item = this.runs.find((run) => run.slot === slot);
      const group = new THREE.Group();
      group.userData.arm = slot.arm;
      // The line of cells: spheres where the run's view prescribes them, along the line.
      const material = new THREE.MeshStandardMaterial({ roughness: 0.42, metalness: 0, toneMapped: false });
      const spheres = new THREE.InstancedMesh(sphereGeometry, material, item.cells.count);
      const matrix = new THREE.Matrix4();
      for (let k = 0; k < item.cells.count; k++) {
        const r = item.cells.radius[k] * 0.94;
        matrix.makeScale(r, r, r).setPosition(place.x0 + item.cells.x[k], place.lineY, 0);
        spheres.setMatrixAt(k, matrix);
        spheres.setColorAt(k, new THREE.Color(0.5, 0.5, 0.5));
      }
      spheres.userData.pick = (hit) => (Number.isInteger(hit.instanceId) ? `${CELL_ID}${slot.arm}:${hit.instanceId}` : null);
      group.add(spheres);
      // The space–time picture: one flat band for each cell and each saved record, from its time to the next.
      const picture = pictureMesh(item, place, bandsNow, this.breaks);
      picture.userData.pick = (hit) => {
        const cell = item.cells.columnAt(hit.point.x - place.x0);
        return cell === null ? null : `${CELL_ID}${slot.arm}:${cell}`;
      };
      // Where on the picture it was pressed: the record whose band holds that place (see picked).
      picture.userData.recordAt = (hit) => this.timeAtY(place, hit.point.y);
      group.add(picture);
      // Its frame, and the tumor's columns marked above the line.
      place.over = (bandsNow[bandsNow.length - 1].to - 1) * (place.top - place.bottom); // the last record's band, past the run's end
      const frame = boxLines(place.x0 - 0.15, place.x1 + 0.15, place.top + 0.15, place.bottom - place.over - 0.15, frameColour);
      frame.userData.unpickable = true;
      group.add(frame);
      const tumor = this.tumorColumns(item);
      if (tumor) {
        const left = place.x0 + tumor.x0, right = place.x0 + tumor.x1, y = place.lineY + 0.78 * PITCH;
        const bracket = lineStrip([[left, y - 0.25 * PITCH], [left, y], [right, y], [right, y - 0.25 * PITCH]], this.ink);
        bracket.userData.unpickable = true;
        group.add(bracket);
      }
      // The clock's cursor across the picture.
      const cursor = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ color: this.ink, toneMapped: false }));
      cursor.scale.set(place.x1 - place.x0 + 1.2 * PITCH, Math.max(0.35, (place.top - place.bottom) / 260), 1);
      cursor.position.set((place.x0 + place.x1) / 2, place.top, 0.6);
      cursor.userData.unpickable = true;
      group.add(cursor);
      this.root.add(group);
      this.pieces.set(slot.arm, { spheres, picture, cursor, place, item });
    }
    // The chosen cell and the one under the pointer: a ring round its sphere and a frame round its column.
    this.marks = { chosen: chosenMarks(this.ink), hover: chosenMarks(this.soft) };
    for (const mark of Object.values(this.marks)) this.root.add(mark.group);
    this.tags = null;
    this.draw();
  }

  /** The tumor's cells, as the record names them (the overlay's `tissue.tumor`), as the columns they span; null where none is named. */
  tumorColumns(item) {
    const named = this.line.tumor?.cells || [];
    const indices = named.map((id) => item.cells.ids.indexOf(id)).filter((index) => index >= 0);
    if (!indices.length) return null;
    return { x0: Math.min(...indices.map((k) => item.cells.x[k] - item.cells.radius[k])), x1: Math.max(...indices.map((k) => item.cells.x[k] + item.cells.radius[k])), count: indices.length };
  }

  /** A time on a picture from a height on it (a press on a picture moves the clock there). */
  timeAtY(place, y) {
    const share = Math.min(1, Math.max(0, (place.top - y) / (place.top - place.bottom)));
    const axis = this.axisNow, t = this.clockRun.t;
    let best = 0;
    for (let k = 0; k < t.length; k++) if (axis.at(t[k]) <= share + 1e-9) best = k;
    return t[best];
  }

  /** Colour the spheres by the record at the clock, and move the cursors and the marks. */
  draw() {
    if (!this.pieces || !this.runs.length) return;
    const index = this.clockRun.indexAt(this.player.time);
    const at = this.axisNow.at(this.clockRun.t[index]);
    const colour = new THREE.Color(), rgb = [0, 0, 0];
    for (const { spheres, cursor, place, item } of this.pieces.values()) {
      for (let k = 0; k < item.cells.count; k++) {
        this.breaks.colour(item.record.at(index, item.cells.columns[k]), rgb);
        spheres.setColorAt(k, colour.setRGB(rgb[0], rgb[1], rgb[2], THREE.SRGBColorSpace));
      }
      spheres.instanceColor.needsUpdate = true;
      // The cursor stands at the top of the band of the record shown: the clock's record, never a place between two.
      cursor.position.y = place.top - at * (place.top - place.bottom);
    }
    this.placeMark(this.marks.chosen, this.selected);
    this.placeMark(this.marks.hover, this.hovered && !(this.selected && this.hovered.arm === this.selected.arm && this.hovered.cell === this.selected.cell) ? this.hovered : null);
    this.placeTags(index);
  }

  placeMark(mark, which) {
    const piece = which ? this.pieces.get(which.arm) : null;
    mark.group.visible = Boolean(piece);
    if (!piece) return;
    const { place, item } = piece, k = which.cell;
    const x = place.x0 + item.cells.x[k], r = item.cells.radius[k];
    mark.ring.position.set(x, place.lineY, r + 0.2);
    mark.ring.scale.setScalar(r * 1.18);
    mark.column.position.set(x, (place.top + place.bottom) / 2, 0.4);
    mark.column.scale.set(2 * r, place.top - place.bottom + 0.4, 1);
  }

  // ------------------------------------------------------------ words on the picture

  /** The names on the picture: each slot's value of the parameter, a run's end in the record's words, the time's ticks, the tumor, and the chosen cell's state. */
  makeTags() {
    const { labels } = this;
    labels.clear();
    const tags = { chosen: null };
    if (!this.places) return (this.tags = tags);
    const narrow = !this.columns, small = this.stage.width < 760;
    let first = true;
    for (const place of this.places) {
      const { slot } = place;
      const middle = (place.x0 + place.x1) / 2;
      if (slot.kind === "refused") {
        if (narrow) {
          // Centred on its place by its own style (a translation of half its height), whatever its measured height.
          labels.add({ text: `${slot.label} · ${lower(this.line.refusedWords)}`, anchor: new THREE.Vector3(middle, place.lineY, 0), kind: "tissue-refused is-centred", priority: 9, lift: 0 }).boost = 1000;
        }
        else {
          labels.add({ text: slot.label, anchor: new THREE.Vector3(middle, place.lineY + 1.5 * PITCH, 0), kind: "tissue-head", priority: 9, lift: 4 });
          labels.add({ text: this.line.refusedWords, anchor: new THREE.Vector3(middle, (place.top + place.bottom) / 2, 0), kind: "tissue-refused is-vertical is-centred", priority: 8, lift: 0 }).boost = 1000;
        }
        continue;
      }
      if (narrow) {
        labels.add({ text: slot.label, anchor: new THREE.Vector3(middle, place.lineY + 1.95 * PITCH, 0), kind: "tissue-head", priority: 9, lift: 0 }).boost = 1000;
        if (slot.end) labels.add({ text: slot.end, anchor: new THREE.Vector3(middle, place.lineY + 0.75 * PITCH, 0), kind: "tissue-end", priority: 8, lift: 2 }).boost = 1000;
      } else {
        labels.add({ text: slot.label, anchor: new THREE.Vector3(middle, place.lineY + 1.5 * PITCH, 0), kind: "tissue-head", priority: 9, lift: 4 }).boost = 1000;
        if (slot.end) labels.add({ text: slot.end, anchor: new THREE.Vector3(middle, place.bottom - (place.over || 0) - 0.6 * PITCH, 0), kind: "tissue-end", priority: 8, lift: -20 });
      }
      if (place.ticks) {
        for (const tick of this.axisNow.ticks) {
          if (small && !tick.major && tick.time - this.axisNow.start !== 3600) continue;
          const words = small && tick.major && tick.at === 1 ? duration(tick.time - this.axisNow.start) : tick.words;
          labels.add({ text: words, anchor: new THREE.Vector3(place.x0 - 0.5 * PITCH, place.top - tick.at * (place.top - place.bottom), 0), kind: "tissue-tick", priority: tick.major ? 6 : 4, lift: 0 });
        }
      }
      first = false;
    }
    return (this.tags = tags);
  }

  /** The chosen cell's state at the clock's record, in the driver's word, beside its sphere. */
  placeTags(index) {
    if (!this.active) return;
    if (!this.tags) this.makeTags();
    const { labels } = this;
    const piece = this.selected ? this.pieces.get(this.selected.arm) : null;
    if (!piece) {
      if (this.tags.chosen) labels.show(this.tags.chosen, false), (this.tags.chosen.hidden = true);
      return;
    }
    const { place, item } = piece, k = this.selected.cell;
    const state = item.states ? item.states.text(index, item.cells.columns[k]) : null;
    const words = `${item.cells.ids[k]}${state ? ` · ${state}` : ""}`;
    const anchor = new THREE.Vector3(place.x0 + item.cells.x[k], place.lineY - item.cells.radius[k] - 0.2 * PITCH, 1);
    if (!this.tags.chosen) {
      this.tags.chosen = labels.add({ text: words, anchor, kind: "tissue-state", priority: 10, lift: 0 });
      this.tags.chosen.boost = 1000;
    }
    const tag = this.tags.chosen;
    tag.hidden = false;
    tag.anchor.copy(anchor);
    labels.setText(tag, words);
    tag.lift = -4; // below its sphere: its own style moves it down by its height
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

  /** Frame the line, and start the clock unless motion is unwanted or the page is held still. */
  enter() {
    const { stage } = this;
    this.build();
    this.home = this.homeView();
    stage.rig.limits = { minDistance: this.home.distance * 0.18, maxDistance: this.home.distance * 3, minPolar: SIDE - 0.7, maxPolar: SIDE + 0.7 };
    stage.rig.setView(this.home);
    if (!this.autoplayed && !stage.reducedMotion && !stage.rig.instant && this.player.time === this.player.start) this.player.play();
    this.autoplayed = true;
  }

  deactivate() {
    this.active = false;
    this.player.pause();
    this.stage.scene.remove(this.root);
    this.labels.clear();
    this.tags = null;
  }

  /** The room changed (a panel opened, the window turned): laid out and framed again, unless the visitor has moved the camera. */
  roomChanged() {
    if (!this.active || !this.runs.length || !this.home) return;
    this.sized = { width: this.stage.width, height: this.stage.height };
    // A window that turned narrow keeps the insets the page set while it was wide (src/ui/viewer.js sets them in renderPanel,
    // which a change of width does not call): on a narrow window the page leaves no room at the sides, so none is kept.
    const insets = this.stage.insets || {};
    if (this.stage.width < 760 && (insets.left || insets.right)) this.stage.setInsets({ bottom: insets.bottom || 0 });
    const { rig } = this.stage;
    const at = rig.flight ? rig.flight.to : rig.view();
    const same = Math.abs(at.distance - this.home.distance) <= 1e-6 * this.home.distance && Math.abs(at.polar - this.home.polar) < 1e-6 && Math.abs(at.azimuth - this.home.azimuth) < 1e-6 && at.target.distanceTo(this.home.target) <= 1e-6 * this.home.distance;
    const columns = this.columns;
    this.build();
    const next = this.homeView();
    this.tags = null;
    if (!same && columns === this.columns) return this.draw();
    this.home = next;
    rig.limits = { ...rig.limits, minDistance: next.distance * 0.18, maxDistance: next.distance * 3 };
    rig.setView(next);
    this.draw();
  }

  /** The camera that frames every slot, its words with it, in the room the page leaves the picture. */
  homeView() {
    const { stage } = this;
    const room = this.room();
    const half = Math.tan((stage.camera.fov * Math.PI) / 360);
    const box = this.box;
    const w = box.x1 - box.x0, hgt = box.y1 - box.y0;
    // The distance that fits the box into the room's pixels, the room being part of the window's height.
    const share = room.height / stage.height, across = room.width / stage.width;
    const distance = Math.max(hgt / (2 * half * share), w / (2 * half * stage.camera.aspect * across)) * 1.04;
    // The room's middle is above or below the window's: the target is moved so that the box stands in the room.
    const perPixel = (2 * distance * half) / stage.height;
    const shiftY = ((room.foot - room.top) / 2) * perPixel;
    return { target: new THREE.Vector3((box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2 - shiftY, 0), distance, azimuth: 0, polar: SIDE };
  }

  setSelection(id) {
    this.panel = id || null;
    const cell = this.cellOf(id);
    this.selected = cell;
    // A press on a picture moves the clock to the record pressed (picked said where, just before).
    if (cell && this.pressedAt?.id === id) {
      this.player.pause();
      this.player.seek(this.pressedAt.time);
    }
    this.pressedAt = null;
    this.draw();
    this.stage?.invalidate();
  }

  /** Where a press on the picture landed (src/ui/viewer.js, before it chooses what was hit): on a picture, the record pressed. */
  picked(hit) {
    const at = hit?.object?.userData.recordAt;
    this.pressedAt = at && hit.id ? { id: hit.id, time: at(hit) } : null;
  }

  setHover(id) {
    const next = this.cellOf(id);
    if (JSON.stringify(next) === JSON.stringify(this.hovered)) return;
    this.hovered = next;
    this.draw();
    this.stage?.invalidate();
  }

  setIsolate() {}

  focus(id) {
    const cell = this.cellOf(id);
    const piece = cell ? this.pieces?.get(cell.arm) : null;
    if (!piece || !this.home) return;
    const { place, item } = piece;
    const target = new THREE.Vector3(place.x0 + item.cells.x[cell.cell], (place.lineY + place.bottom) / 2, 0).lerp(this.home.target, 0.35);
    this.stage.rig.flyTo({ target, distance: this.home.distance * 0.62, azimuth: 0, polar: SIDE }, 900);
  }

  seek(seconds) {
    if (Number.isFinite(seconds) && this.runs.length) this.player.seek(seconds);
  }

  update(dt, time, real = dt) {
    if (!this.active) return false;
    // The window changed size (turned, or made narrow): laid out and framed again, as when the page's cards change the room.
    const { width, height } = this.stage;
    if (this.sized && (this.sized.width !== width || this.sized.height !== height)) this.roomChanged();
    this.sized = { width, height };
    return this.player.tick(real);
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
      label: `${this.line.short}: ${item.slot.label}`,
      entities: [{ id: RUN + item.run.id, label: `The run at ${item.slot.label}` }, ...item.cells.ids.map((name, k) => ({ id: `${CELL_ID}${item.slot.arm}:${k}`, label: `${name} at ${item.slot.short}`, keywords: this.line.tumor?.cells?.includes(name) ? "tumor" : "" }))],
    }));
  }

  entities() {
    return this.sections().flatMap((section) => section.entities);
  }

  describe(id) {
    if (typeof id !== "string") return null;
    if (id.startsWith(RUN)) {
      const item = this.runs.find((run) => run.run.id === id.slice(RUN.length));
      return item ? { ...this.catalogue.describe(id, item.run), eyebrow: this.line.entry.label } : null;
    }
    const cell = this.cellOf(id);
    if (!cell) return null;
    const item = this.runs.find((run) => run.slot.arm === cell.arm);
    const column = item.cells.columns[cell.cell], name = item.cells.ids[cell.cell];
    const index = this.clockRun.indexAt(this.player.time);
    const state = item.states ? item.states.text(index, column) : null;
    const tumor = this.line.tumor?.cells?.includes(name);
    const label = item.record.label;
    return {
      id,
      label: `${name}, at ${item.slot.label}`,
      eyebrow: this.line.entry.label,
      kind: "cell",
      plain: `One cell of the line in the run at ${item.slot.label}. The chart shows its ${lower(label)} at every saved record, as the experiment's driver states it beside the run; the line through it is the clock, and the cell's column in the picture is the same record drawn as colour.`,
      note: `Every point is a saved record, and nothing is interpolated between them. The state is the driver's own (${item.record.stated?.file || "its file"}), never read from the colour.`,
      chips: [{ label: item.slot.label, title: "The run this cell is shown in." }, ...(tumor ? [{ label: "Tumor", title: this.line.tumor.source || "" }] : [])],
      facts: [
        ["Run", item.slot.arm],
        [`${label} at ${clock(this.clockRun.t[index], { precise: true })}`, reading(item.record, item.record.at(index, column)) || "no value"],
        ...(state ? [["State there, as the driver states it", state]] : []),
        ...(item.slot.end ? [[this.line.endsLabel, item.slot.end]] : []),
      ],
      chart: {
        run: item.run,
        record: item.record,
        index: column,
        player: this.player,
        title: label,
        judged: null,
        levels: item.record.marks || [],
        events: [],
        extra: item.states ? (step) => `state ${item.states.text(step, column)}` : null,
      },
      sections: [],
      related: [],
      sources: this.line.sources,
    };
  }

  chrome() {
    const line = this.line;
    const status = this.error ? `The tissue line could not be shown: ${this.error}` : this.loading ? "Loading the tissue line's runs…" : null;
    const revision = this.runs[0]?.run.info.revision;
    const chrome = {
      quiet: true,
      status,
      // The record's first line of the part (its standing: development work, not judged) heads the stamp, so that it is in sight beside the pictures' captions.
      stamp: [line?.says?.[0]?.replace(/\.$/, ""), line?.entry.short || line?.entry.label, revision ? `engine ${revision.slice(0, 8)}` : null].filter(Boolean).join(" · "),
      timeline: this.runs.length ? { player: this.player, eventWord: "event" } : null,
      card: line
        ? {
            heading: line.entry.label,
            stats: [],
            text: line.entry.plain,
            own: () => this.cardParts(),
            choices: this.runs.length ? [{ key: "time-scale", label: "Time down the pictures", options: TIME_SCALES, active: this.scale, set: (value) => this.setScale(value) }] : [],
            sources: line.sources.map((source) => ({ name: source.path, url: this.model.sourceUrl?.(source) || null, holds: source.where, licence: source.revision ? `at ${source.revision.slice(0, 8)}` : "" })),
          }
        : { heading: "The tissue line", stats: [], text: status || "", sources: [] },
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
        said: `The colour is the experiment's own quantity, stated by its driver beside each run (${record.stated?.file || "its file"}) and copied as stated: not a field of the engine. The scale breaks at the criterion's thresholds: one hue below, a grey between, another above. The criterion's own words are in the card.`,
      };
      chrome.legend.keys = [
        { key: "tissue-line", text: "Each run: its cells at the clock's record, and under them its space–time picture, time down; the bar across it is the clock" },
        ...(line.tumor ? [{ key: "tissue-bracket", text: `The bracket: ${lower(line.tumor.label)} (${line.tumor.source})` }] : []),
        ...(line.refused.length ? [{ key: "tissue-refused", text: "A dashed place: a pick an engine check refused, with no run to show" }] : []),
      ];
      chrome.legend.note = { text: this.axisNow?.words || "" };
      // The keys and the note fold under the scale, so that the card keeps its room for the record's lines and the picks.
      chrome.legend.folded = true;
    }
    return chrome;
  }

  /** What the card says beyond the experiment's text: the record's own lines, then each pick in its place. */
  cardParts() {
    const line = this.line;
    if (!line) return [];
    const whole = this.catalogue.experiments.get(line.entry.part_of);
    return [
      // The way back to the example, by its own button: on a phone the tab's list is a select whose chosen option is the example already.
      typeof this.back === "function" && whole ? h("button", { class: "tissue-back", type: "button", onclick: () => this.back() }, `Back to the example's networks`) : null,
      h("ul", { class: "tissue-says" }, line.says.map((said) => h("li", {}, said))),
      // The criterion in its own words, with its source, as the driver's file gives them.
      ...(this.runs[0]?.record.criterion ? [h("details", { class: "tissue-criterion" }, h("summary", {}, "The criterion, in its own words"), h("p", { class: "card-text" }, `“${this.runs[0].record.criterion.words}”`), h("p", { class: "card-text tissue-criterion-source" }, `Its source, as the file gives it: ${this.runs[0].record.criterion.source}`))] : []),
      h(
        "div",
        { class: "tissue-slots", role: "group", "aria-label": "The picks, in the order of D" },
        h("span", { class: "seg-label" }, `Picks · ${line.slots.length}`),
        ...line.slots.map((slot) =>
          h(
            "div",
            { class: `tissue-slot${slot.kind === "refused" ? " is-refused" : ""}`, dataset: { arm: slot.arm } },
            h("b", {}, slot.label),
            h("span", {}, slot.kind === "refused" ? line.refusedWords : slot.end || ""),
            slot.kind === "run" ? h("button", { class: "tissue-open", type: "button", onclick: () => this.onShown?.(RUN + slot.id) }, "Run details") : null
          )
        ),
        h("p", { class: "card-text tissue-ends-said" }, line.endsSaid || `${line.endsLabel}.`)
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
    this.tags = null;
    if (this.active) this.onChrome?.();
    this.stage?.invalidate();
  }

  dispose() {
    disposeTree(this.root);
  }
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

/** One flat band for each cell and each saved record, from its time to the next, in the colour of its value. */
function pictureMesh(item, place, bandsNow, breaks) {
  const { cells, record } = item;
  const count = cells.count * bandsNow.length;
  const positions = new Float32Array(count * 18), colours = new Float32Array(count * 18);
  const height = place.top - place.bottom;
  const colour = new THREE.Color(), rgb = [0, 0, 0];
  let v = 0;
  for (let k = 0; k < cells.count; k++) {
    const x0 = place.x0 + cells.x[k] - cells.radius[k], x1 = place.x0 + cells.x[k] + cells.radius[k];
    for (const band of bandsNow) {
      const y0 = place.top - band.from * height, y1 = place.top - band.to * height;
      breaks.colour(record.at(band.k, cells.columns[k]), rgb);
      colour.setRGB(rgb[0], rgb[1], rgb[2], THREE.SRGBColorSpace);
      for (const [x, y] of [[x0, y0], [x0, y1], [x1, y1], [x0, y0], [x1, y1], [x1, y0]]) {
        positions[v * 3] = x;
        positions[v * 3 + 1] = y;
        positions[v * 3 + 2] = 0;
        colours[v * 3] = colour.r;
        colours[v * 3 + 1] = colour.g;
        colours[v * 3 + 2] = colour.b;
        v++;
      }
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colours, 3));
  geometry.computeBoundingSphere();
  geometry.computeBoundingBox();
  const mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ vertexColors: true, toneMapped: false, side: THREE.DoubleSide }));
  mesh.name = "space-time";
  return mesh;
}

function lineStrip(points, colour) {
  const geometry = new THREE.BufferGeometry().setFromPoints(points.map(([x, y]) => new THREE.Vector3(x, y, 0.3)));
  return new THREE.Line(geometry, new THREE.LineBasicMaterial({ color: colour, toneMapped: false }));
}

function boxLines(x0, x1, y0, y1, colour) {
  return lineStrip([[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]], colour);
}

function dashedBox(x0, x1, y0, y1, colour) {
  const line = lineStrip([[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]], colour);
  line.material = new THREE.LineDashedMaterial({ color: colour, dashSize: 1.6, gapSize: 1.2, toneMapped: false });
  line.computeLineDistances();
  return line;
}

/** A ring round a chosen sphere, and a frame round its column of the picture. */
function chosenMarks(colour) {
  const group = new THREE.Group();
  group.visible = false;
  group.userData.unpickable = true;
  const ring = new THREE.Mesh(new THREE.RingGeometry(0.92, 1.08, 40), new THREE.MeshBasicMaterial({ color: colour, toneMapped: false, side: THREE.DoubleSide }));
  const column = lineStrip([[-0.5, 0.5], [0.5, 0.5], [0.5, -0.5], [-0.5, -0.5], [-0.5, 0.5]], colour);
  group.add(ring, column);
  return { group, ring, column };
}
