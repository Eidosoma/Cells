// tint: each cell of a sheet takes the colour of a saved value, on a ramp of one hue.
// It is the colouring the replay has always had, as a mark of its own: the same share of
// the scale, the same ramp, the same shading of the side walls.

import * as THREE from "../../three.js";
import { shareOf } from "../scale.js";

export const tint = {
  name: "tint",
  channels: ["colour"],
  lives_on: ["cell"],

  /**
   * context (see ./index.js): the sheet, the run, what the run feeds the layer with
   * (`fed.source` is the saved record), how a record's scale is found, and the colours
   * ({ ramp, neutral }: the ramp, and the tone of a cell with no value to show).
   */
  create({ surface, run, fed, scaleOf, colours }) {
    const record = run.records.get(fed.source.id);
    const domain = scaleOf(record);
    const rgb = [0, 0, 0], linear = new THREE.Color();
    let { ramp, neutral } = colours;
    return {
      record,
      domain,
      update(step, valid) {
        paint(surface, (number_) => {
          if (valid) ramp.at(shareOf(record.at(step, number_), domain), rgb);
          else rgb.splice(0, 3, ...neutral); // not a valid record: no value is shown
          return rgb;
        }, linear);
      },
      /** The legend's scale: the ramp with its limits in the unit shown, or one swatch per step of a count. */
      scale(label, write) {
        const { shown, low, high, steps, nice } = domain;
        const scale = { label, unit: shown.unit };
        if (steps) {
          scale.steps = Array.from({ length: steps + 1 }, (_, k) => ({ colour: cssOf(ramp.at(k / steps)), text: String(k) }));
        } else {
          scale.gradient = ramp.css();
          const decimals = nice.step * 1 < 1 ? 1 : 0;
          scale.ticks = [low, (low + high) / 2, high].map((value, k) => ({ at: k / 2, text: write(value * shown.factor, decimals) }));
          scale.marks = (record.marks || []).filter((mark) => mark.value > low && mark.value < high).map((mark) => ({ at: (mark.value - low) / (high - low), text: `${write(mark.value * shown.factor, 1)} ${shown.unit}: ${mark.label}` }));
        }
        return scale;
      },
      setColours(next) {
        ({ ramp, neutral } = next);
      },
      dispose() {},
    };
  },
};

const cssOf = ([r, g, b]) => `rgb(${Math.round(r * 255)}, ${Math.round(g * 255)}, ${Math.round(b * 255)})`;

/** Write one colour per cell into the sheet: its top, and its side walls each with their own shading. */
export function paint(surface, colourOf, linear = new THREE.Color()) {
  const colour = surface.geometry.attributes.color;
  surface.cells.forEach((cell, number_) => {
    const rgb = colourOf(number_);
    const n = cell.inset.length;
    linear.setRGB(rgb[0], rgb[1], rgb[2], THREE.SRGBColorSpace);
    for (let k = 0; k <= n; k++) colour.array.set([linear.r, linear.g, linear.b], (cell.start + k) * 3);
    for (let k = 0; k < n; k++) {
      const wall = cell.walls + k * 4, shade = cell.shade[k];
      linear.setRGB(rgb[0] * shade, rgb[1] * shade, rgb[2] * shade, THREE.SRGBColorSpace);
      for (let corner = 0; corner < 4; corner++) colour.array.set([linear.r, linear.g, linear.b], (wall + corner) * 3);
    }
  });
  colour.needsUpdate = true;
}
