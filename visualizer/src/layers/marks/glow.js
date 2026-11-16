// glow: where energy is dissipated, and how much a second. The run's ledgers of dissipated
// energy only ever grow; the mean rate of one between two records is a power, and a place
// glows the brighter the larger it is. A magnitude with a scale in the legend, not a
// temperature: nothing here says how warm anything is.
//
// Each element that has a ledger glows in its own place, and none is added to another:
//   a band on a border    a junction between two cells, a face between two spaces outside, a
//                         membrane between a cell and the space it faces where both have tiles;
//                         half of it lies on each tile's own top, and none of it on a wall
//   a rim round a cell    a membrane whose outside has no tile on this picture
//   a spot on a cell      the pump of its membrane, and each of its channel populations
//
// The rate is a mean over the interval that ends at the record shown (the `rate` rule), so
// at a run's first record nothing glows. The lens may mark the glow to shine (`shines`); it
// reads without that.

import * as THREE from "../../three.js";
import { roundUp } from "../scale.js";
import { rateDisplay } from "../../replay/format.js";
import { meanRate, restarted } from "./beads.js";

export const FLOOR = 0.02; // a power under this share of the scale is not drawn
export const TONE = { light: "#c8620a", dark: "#ffb44a" }; // one hue for the magnitude, apart from the ramp's and from every ion's
const LEVEL = { quiet: [0.22, 0.6], bold: [0.32, 0.66] }; // the faintest glow drawn, and how much the full scale adds

/** How strongly a place glows for a power on a scale: 0 under the floor, then from the faintest to the full. */
export function glowOf(power, full, strength = "quiet") {
  const share = full > 0 ? Math.min(1, Math.max(0, power) / full) : 0;
  if (!(share >= FLOOR)) return 0;
  const [least, more] = LEVEL[strength] || LEVEL.quiet;
  return least + more * share;
}

/** Whether a ledger ever changes for one entity (one that restarts where a slot is retired may end lower than it began). */
function everGrows(run, record, entity) {
  const first = record.at(0, entity);
  for (let step = 1; step < run.count; step++) if (record.at(step, entity) !== first) return true;
  return false;
}

/**
 * The elements of a run that glow: one for each entity of each ledger that ever grows.
 * `sources` are the ledgers as declared; `spots` those of what lies on a membrane without a
 * place of its own (a pump, a channel population), each as { record, says }. Returns
 * { elements, unplaced }: an element is { record, entity, name, kind, border, cell }.
 */
export function elementsOf(run, sources, spots, world) {
  const elements = [], unplaced = [];
  const each = (record, kind) => {
    const set = run.sets.get(record.set);
    if (!set) return;
    for (let entity = 0; entity < set.ids.length; entity++) {
      if (!everGrows(run, record, entity)) continue;
      const place = world.placeOf(record.set, entity);
      const element = { record, entity, name: set.ids[entity], kind, border: null, cell: place?.cell ?? null };
      if (kind === "spot") {
        if (element.cell === null) unplaced.push(element);
        else elements.push(element);
      } else if (place?.border) elements.push({ ...element, kind: "band", border: place.border });
      else if (element.cell !== null) elements.push({ ...element, kind: "rim" });
      else unplaced.push(element);
    }
  };
  for (const source of sources) {
    const record = run.records.get(source.id);
    if (record) each(record, "band");
  }
  for (const record of spots) each(record, "spot");
  return { elements, unplaced };
}

/** The largest mean power of any element over any interval of the run, in the ledgers' unit a second. */
export function brightestOf(run, elements) {
  let most = 0;
  for (const element of elements) {
    for (let step = 1; step < run.count; step++) {
      const mean = meanRate(run, element.record, element.entity, step);
      if (mean !== null) most = Math.max(most, mean);
    }
  }
  return most;
}

export const glow = {
  name: "glow",
  channels: ["glow"],
  lives_on: ["junction", "face", "membrane", "route"],
  needs_growth: true,

  /**
   * context (see ./index.js): the sheet with its `world`, the run, `fed.sources` (the
   * ledgers as declared) and `fed.extras` (by role "pump" and "channels": the ledgers of
   * what lies on a membrane), the colours and the strength.
   */
  create({ surface, run, fed, colours, strength = "quiet" }) {
    const world = surface.world;
    // A ledger of what lies on a membrane is read only where the run says it is a total that never falls.
    const spots = (fed.extras || []).map((extra) => run.records.get(extra.record)).filter((record) => record && record.kind === "cumulative" && (record.monotone === "non-decreasing" || record.resets));
    const { elements, unplaced } = elementsOf(run, fed.sources || [], spots, world);
    const most = brightestOf(run, elements);
    const shown = rateDisplay(elements[0]?.record.unit || "pJ", most);
    // The rates are differences of numbers stored in 32 bits: a round number they miss by that much is still the scale's end.
    const full = roundUp(most * shown.factor * (1 - 1e-6)) / shown.factor;
    const routes = (fed.sources || []).some((source) => source.lives_on === "route");

    // One mesh: for each vertex its place on the ground, whose height it takes, and how much of its element's glow it shows.
    const xz = [], heights = [], weights = [], owner = [];
    const push = (element, x, z, height, weight) => {
      xz.push(x, z);
      heights.push(height);
      weights.push(weight);
      owner.push(element);
    };
    const top = (cell) => () => surface.cells[cell].height + surface.pitch * 0.02;
    const level = (tile) => (tile.set === "cell" ? top(tile.index) : () => (surface.outside?.level ?? 0) + surface.pitch * 0.02);
    const quad = (index, a, b, c, d) => {
      for (const corner of [a, b, c, a, c, d]) push(index, ...corner);
    };
    const perCell = new Map(); // cell -> how many spots stand on it so far
    elements.forEach((element, index) => {
      if (element.kind === "band") {
        const { border } = element;
        const half = surface.pitch * 0.13, reach = border.length * 0.4;
        const at = (along, across) => [border.mid[0] + border.along[0] * along + border.across[0] * across, border.mid[1] + border.along[1] * along + border.across[1] * across];
        // Two strips, one on each tile's own top: full at the border, nothing at the strip's far edge. Where one
        // tile stands higher than the other, the wall between them carries no glow.
        quad(index, [...at(-reach, -half), level(border.a), 0], [...at(reach, -half), level(border.a), 0], [...at(reach, 0), level(border.a), 1], [...at(-reach, 0), level(border.a), 1]);
        quad(index, [...at(-reach, 0), level(border.b), 1], [...at(reach, 0), level(border.b), 1], [...at(reach, half), level(border.b), 0], [...at(-reach, half), level(border.b), 0]);
      } else if (element.kind === "rim") {
        const cell = surface.cells[element.cell], height = top(element.cell);
        const ring = (share) => cell.inset.map(([x, y]) => [cell.centre[0] + (x - cell.centre[0]) * share, cell.centre[1] + (y - cell.centre[1]) * share]);
        const inner = ring(0.8), middle = ring(0.92), outer = ring(1.02);
        cell.inset.forEach((_, k) => {
          const next = (k + 1) % cell.inset.length;
          quad(index, [...inner[k], height, 0], [...inner[next], height, 0], [...middle[next], height, 1], [...middle[k], height, 1]);
          quad(index, [...middle[k], height, 1], [...middle[next], height, 1], [...outer[next], height, 0], [...outer[k], height, 0]);
        });
      } else {
        // A spot: the spots of one cell stand in a row across its middle.
        const slot = perCell.get(element.cell) || 0;
        perCell.set(element.cell, slot + 1);
        element.slot = slot;
      }
    });
    // The spots are placed once every cell's count is known, so that each row is centred.
    elements.forEach((element, index) => {
      if (element.kind !== "spot") return;
      const cell = surface.cells[element.cell], height = top(element.cell);
      const count = perCell.get(element.cell), radius = surface.pitch * 0.11, step = Math.min(surface.pitch * 0.24, (cell.radius * 1.5) / Math.max(1, count));
      const cx = cell.centre[0] + (element.slot - (count - 1) / 2) * step, cz = cell.centre[1];
      const SIDES = 14;
      for (let k = 0; k < SIDES; k++) {
        const a = (k / SIDES) * Math.PI * 2, b = ((k + 1) / SIDES) * Math.PI * 2;
        push(index, cx, cz, height, 1);
        push(index, cx + Math.cos(a) * radius, cz + Math.sin(a) * radius, height, 0);
        push(index, cx + Math.cos(b) * radius, cz + Math.sin(b) * radius, height, 0);
      }
    });
    const count = weights.length;
    const positions = new Float32Array(Math.max(3, count * 3)), tints = new Float32Array(Math.max(4, count * 4));
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute("color", new THREE.BufferAttribute(tints, 4));
    geometry.setDrawRange(0, count);
    const material = new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, depthTest: false, depthWrite: false, side: THREE.DoubleSide, toneMapped: false });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.frustumCulled = false;
    mesh.renderOrder = 3;
    mesh.userData.unpickable = true;
    mesh.userData.noContact = true;
    surface.root.add(mesh);
    let level_ = strength, tone = new THREE.Color(colours.dark ? TONE.dark : TONE.light);
    let shownAt = { step: 0, valid: false };
    const powers = new Float32Array(Math.max(1, elements.length));

    const draw = () => {
      const { step, valid } = shownAt;
      elements.forEach((element, index) => {
        const mean = valid ? meanRate(run, element.record, element.entity, step) : null;
        element.mean = mean;
        powers[index] = mean === null ? 0 : glowOf(mean, full, level_);
      });
      for (let vertex = 0; vertex < count; vertex++) {
        positions[vertex * 3] = xz[vertex * 2];
        positions[vertex * 3 + 1] = heights[vertex]();
        positions[vertex * 3 + 2] = xz[vertex * 2 + 1];
        tints[vertex * 4] = tone.r;
        tints[vertex * 4 + 1] = tone.g;
        tints[vertex * 4 + 2] = tone.b;
        tints[vertex * 4 + 3] = powers[owner[vertex]] * weights[vertex];
      }
      geometry.attributes.position.needsUpdate = true;
      geometry.attributes.color.needsUpdate = true;
    };

    return {
      elements,
      unplaced,
      full,
      shown,
      shines: [mesh],
      get floor() {
        return FLOOR * full;
      },
      update(step, valid) {
        shownAt = { step, valid };
        draw();
      },
      /** The interval the powers shown are means over: [from, to] in the run's seconds, or null at the first record. */
      interval() {
        return shownAt.step >= 1 ? [run.t[shownAt.step - 1], run.t[shownAt.step]] : null;
      },
      /** The numbers behind each glowing element at the record shown, for the panel. */
      readings() {
        const { step } = shownAt;
        return elements.map((element, index) => ({
          name: element.name,
          record: element.record.id,
          label: element.record.label,
          kind: element.kind,
          unit: element.record.unit,
          before: step >= 1 ? element.record.at(step - 1, element.entity) : null,
          now: element.record.at(step, element.entity),
          seconds: step >= 1 ? run.t[step] - run.t[step - 1] : null,
          mean: element.mean ?? null,
          reset: restarted(run, element.record, element.entity, step),
          share: element.mean === null || element.mean === undefined ? null : Math.min(1, Math.max(0, element.mean) / full),
          glow: powers[index],
        }));
      },
      /** The legend's lines: what the brightest glow stands for, where a glow may stand, and what a value for a route is. */
      keys(write) {
        const digits = full * shown.factor < 10 ? 1 : 0;
        const lines = [{ key: "glow", text: `A glow where energy is dissipated: the brighter, the more a second. The brightest stands for ${write(full * shown.factor, digits)} ${shown.unit}; under ${write(FLOOR * full * shown.factor, digits + 1)} ${shown.unit} nothing glows. A magnitude, not a temperature` }];
        if (elements.some((element) => element.kind === "rim")) lines.push({ key: "glow-rim", text: "A glowing rim round a cell: at its membrane" });
        if (elements.some((element) => element.kind === "spot")) lines.push({ key: "glow-spot", text: "A glowing spot on a cell: at its pump, or at one of its channel populations; the panel names each" });
        if (routes) lines.push({ key: "glow-route", text: "A value for a route is an exact attribution of its row's fall in free energy between the routes that move it. It cannot be measured apart" });
        if ((fed.sources || []).some((source) => source.resets) || spots.some((record) => record.resets)) lines.push({ key: "glow-reset", text: "Where a cell's slot is retired its totals restart at nought: no glow is drawn for the interval in which that happens" });
        return lines;
      },
      setStrength(next) {
        level_ = next;
        draw();
      },
      setColours(next) {
        tone = new THREE.Color(next.dark ? TONE.dark : TONE.light);
        draw();
      },
      dispose() {
        surface.root.remove(mesh);
        geometry.dispose();
        material.dispose();
      },
    };
  },
};
