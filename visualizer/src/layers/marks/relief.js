// relief: each cell of a sheet stands as high as a saved value. Quiet, it is the modest
// height the replay has always had; bold, the same values stand several cells high, with a
// bar beside the sheet that says how much of the quantity one stretch of height is, and a
// line at each value the experiment itself marks on the record (the voltage above which it
// counts a cell as written), drawn where the sheet crosses it.
// Nothing is smoothed between cells: a cell's height is its own saved value.

import * as THREE from "../../three.js";
import { shareOf } from "../scale.js";

// How far above the lowest cell the highest stands when the relief is bold, in cells across.
// Quiet, it is the height the sheet has always had (surface.high), so that nothing changes.
export const BOLD_RISE = 2.6;

/** The rise of the scale's top over its bottom, in the sheet's units, for a strength. */
export const riseOf = (surface, strength) => (strength === "bold" ? BOLD_RISE * surface.pitch : surface.high - surface.low);

/** The height of a cell: `low` for the bottom of the scale, `low + rise` for its top. */
export function heightOf(share, low, rise) {
  return low + rise * share;
}

/** A round stretch of the quantity for the bar: about a third of the scale, as 1, 2 or 5 times a power of ten. */
export function barStretch(span) {
  if (!(span > 0)) return 0;
  const rough = span / 3;
  const power = Math.pow(10, Math.floor(Math.log10(rough)));
  return [10, 5, 2, 1].map((size) => size * power).find((size) => size <= rough * 1.5) ?? power;
}

export const relief = {
  name: "relief",
  channels: ["height"],
  lives_on: ["cell"],

  /** context (see ./index.js): `fed.source` is the saved record that raises the sheet; colours.ink is for the bar. */
  create({ surface, run, fed, scaleOf, strength = "quiet", colours }) {
    const record = run.records.get(fed.source.id);
    const domain = scaleOf(record);
    const shown = domain.shown || { unit: "", factor: 1 };
    const span = (domain.high - domain.low) * shown.factor;
    let rise = riseOf(surface, strength), bold = strength === "bold";
    const bar = makeBar(surface, colours.ink);
    // The values the experiment marks on this record, within the scale: each gets a line.
    const levels = (record.marks || []).filter((mark) => mark.value > domain.low && mark.value < domain.high).map((mark) => ({ ...mark, line: makeLine(surface, colours.ink) }));
    const place = () => {
      // The bar stands beside the sheet, at its near right, and only when height is the main reading.
      const stretch = barStretch(span);
      const tall = span > 0 ? (stretch / span) * rise : 0;
      bar.group.visible = bold && tall > 0;
      bar.group.position.set(surface.extent * 1.04, surface.low, surface.extent * 0.66);
      bar.stem.scale.set(1, Math.max(tall, 1e-6), 1);
      bar.top.position.y = tall;
      bar.text = `${Number(stretch.toPrecision(3))} ${shown.unit}`.trim();
      bar.anchor.set(bar.group.position.x, surface.low + tall, bar.group.position.z);
    };
    place();
    return {
      record,
      domain,
      /** The height of the tallest cell this relief can draw: what stands over the sheet clears it. */
      get ceiling() {
        return surface.low + rise;
      },
      /** The bar's reading and where it stands, while it is shown. */
      get bar() {
        return bar.group.visible ? { text: bar.text, anchor: bar.anchor } : null;
      },
      update(step, valid) {
        raise(surface, (number_) => (valid ? heightOf(shareOf(record.at(step, number_), domain), surface.low, rise) : surface.low));
        // A line at each marked value: along every seam with a cell above the value on one side
        // and a cell below it on the other, at the height the value itself stands at.
        for (const level of levels) {
          const crossed = bold && valid ? crossings(surface.links, (number_) => record.at(step, number_), level.value) : [];
          level.count = crossed.length;
          drawLine(level.line, crossed, heightOf(shareOf(level.value, domain), surface.low, rise), surface.pitch * 0.07);
        }
      },
      /** The legend's lines for what a bold relief adds to the sheet. */
      keys(write) {
        if (!bold) return [];
        const unit = shown.unit ? ` ${shown.unit}` : "";
        return levels.map((level) => ({ key: "level", text: `A line where the sheet crosses ${write(level.value * shown.factor, 1)}${unit}: ${level.label}` }));
      },
      /** How many seams each marked value is crossed at, at the record last drawn. */
      get crossed() {
        return levels.map((level) => level.count || 0);
      },
      setStrength(next) {
        bold = next === "bold";
        rise = riseOf(surface, next);
        place();
      },
      setColours(next) {
        bar.material.color.copy(next.ink);
        for (const level of levels) level.line.material.color.copy(next.ink);
      },
      dispose() {
        surface.root.remove(bar.group);
        bar.material.dispose();
        for (const mesh of bar.group.children) mesh.geometry.dispose();
        for (const level of levels) {
          surface.root.remove(level.line);
          level.line.geometry.dispose();
          level.line.material.dispose();
        }
      },
    };
  },
};

/** Write one height per cell into the sheet: the top of each prism, and the top of its side walls. */
export function raise(surface, heightAt) {
  const position = surface.geometry.attributes.position;
  surface.cells.forEach((cell, number_) => {
    const height = heightAt(number_);
    cell.height = height;
    cell.top.y = height;
    const n = cell.inset.length;
    for (let k = 0; k <= n; k++) position.array[(cell.start + k) * 3 + 1] = height;
    for (let k = 0; k < n; k++) {
      const wall = cell.walls + k * 4;
      position.array[wall * 3 + 1] = height;
      position.array[(wall + 1) * 3 + 1] = height;
    }
  });
  position.needsUpdate = true;
}

/**
 * The seams a value is crossed at: those between a cell above it and a cell at or below it.
 * Each is given as the two ends of the seam's middle line, [[x, y], [x, y]].
 */
export function crossings(links, valueOf, level) {
  const out = [];
  for (const link of links) {
    if (valueOf(link.a) > level === valueOf(link.b) > level) continue;
    const [a0, a1, b1, b0] = link.points;
    out.push([[(a0[0] + b0[0]) / 2, (a0[1] + b0[1]) / 2], [(a1[0] + b1[0]) / 2, (a1[1] + b1[1]) / 2]]);
  }
  return out;
}

/** A mesh that can hold a flat band along every link of the sheet; it draws none until told. */
function makeLine(surface, ink) {
  const geometry = new THREE.BufferGeometry();
  const most = Math.max(1, surface.links.length);
  geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(most * 12), 3));
  const index = [];
  for (let k = 0; k < most; k++) index.push(k * 4, k * 4 + 1, k * 4 + 2, k * 4, k * 4 + 2, k * 4 + 3);
  geometry.setIndex(index);
  geometry.setDrawRange(0, 0);
  const mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ color: ink.clone(), transparent: true, opacity: 0.92, side: THREE.DoubleSide }));
  mesh.frustumCulled = false;
  mesh.userData.unpickable = true;
  mesh.renderOrder = 3;
  surface.root.add(mesh);
  return mesh;
}

/** Lay a band of a given width along each edge ([[x, y], [x, y]]), flat, at one height. */
function drawLine(mesh, edges, height, width) {
  const position = mesh.geometry.attributes.position;
  edges.forEach(([[ax, ay], [bx, by]], k) => {
    const length = Math.hypot(bx - ax, by - ay) || 1;
    const ux = (bx - ax) / length, uy = (by - ay) / length;
    const nx = (-uy * width) / 2, ny = (ux * width) / 2;
    // A little longer than the seam, so that the bands of neighbouring seams meet.
    const sx = ax - ux * width, sy = ay - uy * width, ex = bx + ux * width, ey = by + uy * width;
    position.array.set([sx + nx, height, sy + ny, ex + nx, height, ey + ny, ex - nx, height, ey - ny, sx - nx, height, sy - ny], k * 12);
  });
  position.needsUpdate = true;
  mesh.geometry.setDrawRange(0, edges.length * 6);
}

/** A thin upright bar with a foot and a cap: a ruler for height. */
function makeBar(surface, ink) {
  const material = new THREE.MeshBasicMaterial({ color: ink.clone(), transparent: true, opacity: 0.9 });
  const thick = surface.pitch * 0.07;
  const stem = new THREE.Mesh(new THREE.BoxGeometry(thick, 1, thick).translate(0, 0.5, 0), material);
  const cap = () => new THREE.Mesh(new THREE.BoxGeometry(thick * 4.2, thick * 0.9, thick), material);
  const foot = cap(), top = cap();
  const group = new THREE.Group();
  group.add(stem, foot, top);
  group.userData.unpickable = true;
  for (const mesh of [stem, foot, top]) mesh.userData.unpickable = true;
  group.visible = false;
  surface.root.add(group);
  return { group, stem, top, material, text: "", anchor: new THREE.Vector3() };
}
