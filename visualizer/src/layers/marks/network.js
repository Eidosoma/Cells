// network: the junctions of a sheet drawn as a network. Each junction is a line between the
// middles of its two cells, and the line carries the junction's own number at the record shown:
// its conductance, or its gate where that is what the run saved, by the line's width (the
// legend gives the scale; a chosen cell's panel gives each of its junctions' number). What flows
// through a junction (Transfers, ./stream.js) runs along the same line, over it.
//
// Two ways were weighed for carrying the number (17 November 2026): the line's width, and its
// strength (how dark or see-through it is). Width was chosen: a width is read as an amount at a
// glance and compared between two lines side by side, a strength much less surely, and the
// colour stays free for what flows along the line, which wears its species' colour. A junction
// whose number is nought is a hairline, drawn fainter, so that a shut junction is still seen to
// be there; a junction the run has not formed is not drawn at all.
//
// On a sheet of many cells the lines make a mesh: every pair of neighbours a junction joins has
// its line, as thin as the picture's pitch allows, and where all are alike the mesh is even, which
// is what the run says. Nothing is left out for the number of cells.

import * as THREE from "../../three.js";
import { roundUp } from "../scale.js";

const SIZE = { quiet: 1, bold: 1.4 };
/** A line's width at nought and at the top of its scale, as a share of the sheet's pitch. */
export const WIDTH = { least: 0.02, most: 0.14 };
/** How much of the way from one cell's middle to the other's a line covers, about the border between them: a gap is left at each middle, so that on a sheet the lines of a row of junctions read one by one and do not run together into one long line. */
export const SPAN = 0.62;
/** Under this share of its scale a junction counts as shut: a hairline, drawn fainter. */
export const SHUT = 0.02;

/**
 * The scale of a junction's number: a gate (unit 1) runs from shut, nought, to fully open, one;
 * any other number from nought to a round number at or above the largest the run saved.
 */
export function isGate(record) {
  return record.unit === "1" || (!record.unit && /gate/i.test(record.id));
}

export function fullOf(record, values) {
  if (isGate(record)) return 1;
  const most = values.reduce((top, value) => (Number.isFinite(value) ? Math.max(top, Math.abs(value)) : top), 0);
  return most > 0 ? roundUp(most) : 1;
}

/** How wide a junction's line is drawn, as a share of the pitch, for its number beside the scale's top; and whether it counts as shut. */
export function lineOf(value, full) {
  if (!Number.isFinite(value)) return null;
  const share = Math.min(1, Math.max(0, value / full));
  return { share, width: WIDTH.least + (WIDTH.most - WIDTH.least) * share, shut: share < SHUT };
}

export const network = {
  name: "network",
  channels: ["links"],
  lives_on: ["junction"],

  /**
   * context (see ./index.js): the sheet (`surface.links`: each junction between two cells, with
   * its cells `a` and `b`), the run, `fed.source` (the junctions' saved number), `shown` (how a
   * record's unit is written), the strength and the page's colours.
   */
  create({ surface, run, fed, shown: shownOf, strength = "quiet", colours }) {
    const links = surface.links;
    const record = run.records.get(fed.source.id);
    const shown = shownOf(record);
    const values = [];
    for (let step = 0; step < run.count; step++) for (const link of links) values.push(record.at(step, link.link));
    const full = fullOf(record, values);
    const group = new THREE.Group();
    group.userData.unpickable = true;
    // A flat bar for each junction, laid from one cell's middle to the other's, under what flows along it.
    const bar = new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2);
    const material = new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.72, depthWrite: false, side: THREE.DoubleSide, toneMapped: false });
    const faint = material.clone();
    faint.opacity = 0.35;
    const make = (look) => {
      const mesh = new THREE.InstancedMesh(bar, look, Math.max(1, links.length));
      mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      mesh.setColorAt(0, colours.ink);
      mesh.frustumCulled = false;
      mesh.userData.unpickable = true;
      mesh.renderOrder = 4;
      mesh.count = 0;
      group.add(mesh);
      return mesh;
    };
    const open = make(material), shut = make(faint);
    surface.root.add(group);
    let size = SIZE[strength], ink = colours.ink.clone(), ground = colours.ground.clone(), by = "width";
    const tone = new THREE.Color();
    // Ink or ground, whichever stands out more from the two cells' colours of the moment (as the wedges choose).
    const light = (r, g, b) => 0.2126 * r + 0.7152 * g + 0.0722 * b;
    const apart = (one, other) => (Math.max(one, other) + 0.05) / (Math.min(one, other) + 0.05);
    const toneOn = (link) => {
      const tops = surface.geometry?.attributes?.color?.array;
      if (!tops) return ink;
      const of = (cell) => { const at = surface.cells[cell].start * 3; return light(tops[at], tops[at + 1], tops[at + 2]); };
      const here = (of(link.a) + of(link.b)) / 2;
      return apart(here, light(ink.r, ink.g, ink.b)) >= apart(here, light(ground.r, ground.g, ground.b)) ? ink : ground;
    };
    const matrix = new THREE.Matrix4(), position = new THREE.Vector3(), turn = new THREE.Quaternion(), scale = new THREE.Vector3(), way = new THREE.Vector3(), along = new THREE.Vector3(1, 0, 0);
    const ends = [new THREE.Vector3(), new THREE.Vector3()];
    let shownStep = { step: 0, valid: false };
    const counts = { open: 0, shut: 0 };
    const draw = () => {
      const { step, valid } = shownStep;
      counts.open = counts.shut = 0;
      const lift = surface.pitch * 0.025;
      for (const link of links) {
        const line = valid ? lineOf(record.at(step, link.link), full) : null;
        if (!line) continue;
        const mesh = line.shut ? shut : open, at = line.shut ? counts.shut++ : counts.open++;
        // From the middle of one cell's top to the other's, a little above both.
        ends[0].copy(surface.cells[link.a].top);
        ends[1].copy(surface.cells[link.b].top);
        position.addVectors(ends[0], ends[1]).multiplyScalar(0.5);
        position.y += lift;
        way.subVectors(ends[1], ends[0]);
        const length = way.length();
        turn.setFromUnitVectors(along, way.normalize());
        // The way weighed beside width, kept to be compared: one width, the number in how strongly the line is drawn.
        const width = by === "strength" ? (WIDTH.least + WIDTH.most) / 2 : line.width;
        mesh.setMatrixAt(at, matrix.compose(position, turn, scale.set(length * SPAN, 1, surface.pitch * width * size)));
        const on = toneOn(link), off = on === ink ? ground : ink;
        mesh.setColorAt(at, by === "strength" ? tone.copy(off).lerp(on, 0.15 + 0.85 * line.share) : on);
      }
      open.count = counts.open;
      shut.count = counts.shut;
      for (const mesh of [open, shut]) {
        mesh.instanceMatrix.needsUpdate = true;
        if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
      }
    };

    return {
      record,
      full,
      counts,
      update(step, valid) {
        shownStep = { step, valid };
        draw();
      },
      /** Each junction's number at the record shown, with the names of its two cells: for a chosen cell's panel and the layers' panel. */
      readings() {
        const { step, valid } = shownStep;
        const cells = run.sets.get("cell")?.ids || [];
        const names = run.sets.get(fed.source.set)?.ids || [];
        return links.map((link) => {
          const value = valid ? record.at(step, link.link) : null;
          const line = value === null ? null : lineOf(value, full);
          return { name: names[link.link] ?? `junction ${link.link}`, a: link.a, b: link.b, between: [cells[link.a], cells[link.b]], value, share: line ? line.share : null, shut: line ? line.shut : null };
        });
      },
      /** A number as the legend and the panels write it, in the record's unit. */
      write(value, write) {
        return `${write(value * shown.factor, 2)}${shown.unit ? ` ${shown.unit}` : ""}`;
      },
      /** The legend's lines: what a line is, what its width stands for and the scale. */
      keys(write) {
        const name = (record.label || record.id).replace(/^Junction /, "junction ").toLowerCase();
        const gate = isGate(record);
        return [
          { key: "link", text: `A line joins the two cells of each junction; its width is the ${name}${gate ? ": full width fully open (1), a hairline shut (0)" : `: full width ${this.write(full, write)}, a hairline nought`}` },
          { key: "link-shut", text: `A faint hairline: under ${write(SHUT * full * shown.factor, 2)}${shown.unit ? ` ${shown.unit}` : ""}, ${gate ? "shut" : "next to nothing"}. A chosen cell's panel gives each of its junctions' number` },
        ];
      },
      setStrength(next) {
        size = SIZE[next];
        draw();
      },
      /** How the number is carried: "width" (the page's) or "strength" (weighed beside it, 17 November 2026; kept to be compared). */
      setBy(next) {
        by = next === "strength" ? "strength" : "width";
        draw();
      },
      setColours(next) {
        ink = next.ink.clone();
        ground = next.ground.clone();
        draw();
      },
      dispose() {
        surface.root.remove(group);
        bar.dispose();
        material.dispose();
        faint.dispose();
        for (const mesh of [open, shut]) mesh.dispose();
      },
    };
  },
};
