// arrows: on a piece of one membrane, for each ion the two terms of its electrochemical
// potential difference and what is left of them, each as an arrow through the membrane,
// as long as the term is large, in millivolts. An arrow points the way the ion itself is
// driven: up, out of the cell, or down, into it. That way is read from the term in J/mol,
// never from the millivolts (dividing by z F turns a negative ion's sign round).
//
// Three arrows stand side by side for an ion: hollow for the push of its concentration
// difference, faint for the pull of the voltage, solid for what is left. Where less than a
// millivolt is left, a ring stands in the arrow's place: the ion is in balance.
//
// An arrow crosses the membrane where the piece shows it in section, at its near edge: it
// enters at one face and stands out from the other. How far it stands out from that face is
// its size; the part inside the membrane is the same for every arrow.
//
// An arrow is a drive, not a flow: it never moves. Its length changes only with the saved
// record that is shown.

import * as THREE from "../../three.js";
import { pushPull, largest, membranesOf } from "../membrane.js";
import { roundUp } from "../scale.js";
import { barStretch } from "./relief.js";

export const BALANCE = 0.001; // volts: under this, what is left is drawn as a ring
const SHAFT = { quiet: 0.05, bold: 0.075 }; // half the width of an arrow's shaft, in the piece's units
const LINE = { quiet: 0.024, bold: 0.03 }; // the width of a hollow arrow's line
const LANES = { from: -0.95, to: 1.62 }; // where the ions stand along the piece: the left end is kept for "Outside" and "Inside"
const TERMS = ["concentration", "electrical", "sum"];

/**
 * The outline of one arrow at x: [[x, y], …], seven corners from its foot round its head
 * and back. It enters the membrane at one face (`thick` / 2 from the middle), crosses it,
 * and stands `length` out from the other face; `up` is out of the cell. A term smaller
 * than a head has a head as long as the term, standing on the face.
 */
export function arrowOutline(x, length, half, up, thick = 0) {
  const sign = up ? 1 : -1, head = 2.3 * half, neck = Math.min(3.2 * half, length);
  const foot = -sign * (thick / 2), tip = sign * (thick / 2 + length), y = tip - sign * neck;
  return [[x - half, foot], [x - half, y], [x - head, y], [x, tip], [x + head, y], [x + half, y], [x + half, foot]];
}

/** Where the ions stand along the piece: for each of `count`, its middle and how far its three arrows stand apart. */
export function lanes(count) {
  const span = LANES.to - LANES.from, step = span / Math.max(1, count);
  return Array.from({ length: count }, (_, k) => ({ x: LANES.from + (k + 0.5) * step, apart: Math.min(0.27, step * 0.32) }));
}

export const arrows = {
  name: "arrows",
  channels: ["arrows"],
  lives_on: ["membrane"],
  surface: "membrane",

  /**
   * context: surface (the close-up's piece: { root, piece, order, label }), run, fed (what
   * the run feeds the rule `potential terms` with), membrane (the index of the membrane
   * shown), strength, colours ({ ink, ion(id) }), memo (keeps a run's scale between cells).
   */
  create({ surface, run, fed, membrane, strength = "quiet", colours, memo = (key, make) => make() }) {
    const reader = pushPull(run, fed);
    const species = reader.species;
    const { piece, order } = surface;
    const face = piece.thick / 2, front = piece.front;
    // One scale for the whole run: the largest term of any ion at any membrane, at any valid record, rounded up.
    const full = memo("arrows-full", () => {
      const count = membranesOf(run).ids.length;
      const most = largest(run, count, (step, index) => {
        let top = 0;
        for (const term of reader.at(step, index)) if (term) top = Math.max(top, term.size.concentration, term.size.electrical, term.size.sum);
        return top;
      });
      return roundUp(most * 1000) / 1000;
    });
    const perVolt = piece.reach / full; // the piece's units for a volt
    const place = lanes(species.length);

    const material = (opacity) => new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity, depthTest: false, depthWrite: false, side: THREE.DoubleSide });
    const buffer = (triangles) => {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(triangles * 9), 3));
      geometry.setAttribute("color", new THREE.BufferAttribute(new Float32Array(triangles * 9), 3));
      geometry.setDrawRange(0, 0);
      return geometry;
    };
    // Per ion: a solid arrow (3 triangles) or a ring (40), a hollow arrow's lines (14); and a faint arrow (3).
    const solid = new THREE.Mesh(buffer(Math.max(1, species.length) * 60 + 12), material(1));
    const faint = new THREE.Mesh(buffer(Math.max(1, species.length) * 3), material(0.45));
    const group = new THREE.Group();
    group.renderOrder = order.group;
    group.position.z = front; // the plane of the piece's near edge
    for (const mesh of [faint, solid]) {
      mesh.renderOrder = order.arrows;
      mesh.frustumCulled = false;
      mesh.userData.unpickable = true;
      group.add(mesh);
    }
    surface.root.add(group);

    let half = SHAFT[strength], line = LINE[strength], bold = strength === "bold", ink = colours.ink.clone(), ionOf = colours.ion;
    const names = species.map((id, k) => surface.label({ text: id, at: [place[k].x, face + piece.reach + 0.08, front], kind: "closeup label-closeup-ion", lift: 2 }));
    // In bold, each of the two parts carries its own number at its tip.
    const numbers = species.map(() => [surface.label({ kind: "closeup label-closeup-number" }), surface.label({ kind: "closeup label-closeup-number" })]);
    // A bar beside the piece says how many millivolts a stretch of arrow is.
    const stretch = barStretch(full * 1000) / 1000;
    const barX = piece.width / 2 + 0.24, barTall = stretch * perVolt;
    const barLabel = surface.label({ text: `${Number((stretch * 1000).toPrecision(3))} mV`, at: [barX, face + barTall + 0.04, front], kind: "closeup label-closeup-number", lift: 1 });

    const writer = (mesh) => {
      const position = mesh.geometry.attributes.position.array, colour = mesh.geometry.attributes.color.array;
      let at = 0;
      return {
        triangle(a, b, c, tone) {
          if (at + 9 > position.length) return;
          position.set([a[0], a[1], 0, b[0], b[1], 0, c[0], c[1], 0], at);
          for (let k = 0; k < 3; k++) colour.set([tone.r, tone.g, tone.b], at + k * 3);
          at += 9;
        },
        quad(a, b, c, d, tone) {
          this.triangle(a, b, c, tone);
          this.triangle(a, c, d, tone);
        },
        /** A line of a given width from one point to another, a little longer at both ends so that corners close. */
        stroke(a, b, width, tone) {
          const dx = b[0] - a[0], dy = b[1] - a[1], length = Math.hypot(dx, dy) || 1;
          const ux = dx / length, uy = dy / length, nx = (-uy * width) / 2, ny = (ux * width) / 2, ex = (ux * width) / 2, ey = (uy * width) / 2;
          this.quad([a[0] - ex + nx, a[1] - ey + ny], [b[0] + ex + nx, b[1] + ey + ny], [b[0] + ex - nx, b[1] + ey - ny], [a[0] - ex - nx, a[1] - ey - ny], tone);
        },
        /** A filled arrow from its outline. */
        fill(points, tone) {
          this.quad(points[0], points[1], points[5], points[6], tone);
          this.triangle(points[2], points[3], points[4], tone);
        },
        done() {
          mesh.geometry.setDrawRange(0, at / 3);
          mesh.geometry.attributes.position.needsUpdate = true;
          mesh.geometry.attributes.color.needsUpdate = true;
        },
      };
    };
    const words = (volts, way) => (volts < BALANCE ? "in balance" : `${Math.round(volts * 1000)} mV ${way}`);
    let last = null;

    return {
      full,
      species,
      missing: reader.missing,
      /** The terms of every ion at the record last drawn, as the rule gave them; null at a record that is not valid. */
      get readings() {
        return last;
      },
      /** The same for any record: what the panel and the checks read. */
      at: (step) => reader.at(step, membrane),
      update(step, valid) {
        const strong = writer(solid), soft = writer(faint);
        last = valid ? reader.at(step, membrane) : null;
        species.forEach((id, k) => {
          const term = last ? last[k] : null, tone = ionOf(id), { x, apart } = place[k];
          for (const label of numbers[k]) label.show(false);
          if (!term) {
            names[k].set(last ? `${id}\nno value` : `${id}\nnot a valid record`);
            return;
          }
          const at = [x - apart, x, x + apart];
          TERMS.forEach((name, n) => {
            const volts = term.size[name], up = term.drives[name] === "out", length = volts * perVolt;
            if (name === "sum") {
              if (volts < BALANCE) {
                // In balance: a ring where the arrow would stand.
                const radius = 2 * half + 0.03;
                for (let s = 0; s < 20; s++) {
                  const a = (s / 20) * Math.PI * 2, b = ((s + 1) / 20) * Math.PI * 2;
                  strong.stroke([at[n] + radius * Math.cos(a), radius * Math.sin(a)], [at[n] + radius * Math.cos(b), radius * Math.sin(b)], line, tone);
                }
              } else strong.fill(arrowOutline(at[n], length, half * 1.6, up, piece.thick), tone);
              return;
            }
            if (!(volts > 0)) return;
            const outline = arrowOutline(at[n], length, half, up, piece.thick);
            if (name === "concentration") outline.forEach((point, p) => p + 1 < outline.length && strong.stroke(point, outline[p + 1], line, tone));
            else soft.fill(outline, tone);
            if (bold && volts >= BALANCE) {
              const label = numbers[k][n];
              label.set(String(Math.round(volts * 1000)));
              label.move(at[n], (up ? 1 : -1) * (face + length + 0.03), front);
              label.below(!up);
              label.show(true);
            }
          });
          names[k].set(`${id}\n${words(term.size.sum, term.drives.sum)}`);
        });
        // The bar: a stem with a foot and a cap, in the page's ink.
        const thin = 0.022, cap = 0.07;
        strong.quad([barX - thin / 2, face], [barX + thin / 2, face], [barX + thin / 2, face + barTall], [barX - thin / 2, face + barTall], ink);
        for (const y of [face, face + barTall]) strong.quad([barX - cap, y - thin / 2], [barX + cap, y - thin / 2], [barX + cap, y + thin / 2], [barX - cap, y + thin / 2], ink);
        strong.done();
        soft.done();
      },
      /** The legend's lines: the ions with their colours, and what each of the three arrows is. */
      keys(write) {
        const chips = species.map((id) => ({ label: id, colour: colours.ionCss(id) }));
        const lines = [
          { key: "ions", chips, text: "Up is out of the cell, down is into it" },
          { key: "arrow-hollow", text: "Hollow: the push of the ion's concentration difference" },
          { key: "arrow-faint", text: "Faint: the pull of the voltage on it" },
          { key: "arrow-solid", text: `Solid: what is left of the two. The longest arrow stands for ${write(full * 1000, 0)} mV; a ring where under ${write(BALANCE * 1000, 0)} mV is left` },
        ];
        for (const item of reader.missing) lines.push({ key: "none", text: `${item.id}: not drawn. This run did not save ${item.lacks}` });
        return lines;
      },
      /** What the three arrows are, in a line for the close-up itself. */
      note() {
        return "Hollow arrow: the push of the concentration difference. Faint: the pull of the voltage. Solid: what is left.";
      },
      setStrength(next) {
        half = SHAFT[next];
        line = LINE[next];
        bold = next === "bold";
      },
      setColours(next) {
        ink = next.ink.clone();
        ionOf = next.ion;
        colours = next;
      },
      dispose() {
        surface.root.remove(group);
        for (const mesh of [solid, faint]) {
          mesh.geometry.dispose();
          mesh.material.dispose();
        }
        for (const label of [...names, ...numbers.flat(), barLabel]) label.remove();
      },
    };
  },
};
