// fog: how much of a secreted species each place holds. Each cell takes the colour of the
// amount saved for it, on a ramp of one hue that starts at nought; where the picture gives
// the spaces outside the cells a tile of their own (../world.js), each of those takes the
// colour of its own saved amount on the same scale. A level, so nothing moves.
//
// An amount, not a concentration: two places of different volume with the same colour do
// not hold the species equally dense. The legend says so.
//
// With it go the run's ledgers of the same species, where it saved them (what was made in a
// cell, what was cleared there, what was cleared outside): the mark draws none of them and
// gives each as a number for the panel.

import * as THREE from "../../three.js";
import { shareOf } from "../scale.js";
import { display, niceDomain } from "../../replay/format.js";
import { paint } from "./tint.js";

/** Write one colour for each tile of the spaces outside the cells. */
export function paintOutside(surface, colourOf, linear = new THREE.Color()) {
  const outside = surface.outside;
  if (!outside) return;
  const colour = outside.geometry.attributes.color;
  outside.tiles.forEach((tile, number_) => {
    const rgb = colourOf(number_);
    linear.setRGB(rgb[0], rgb[1], rgb[2], THREE.SRGBColorSpace);
    for (let k = 0; k <= tile.inset.length; k++) colour.array.set([linear.r, linear.g, linear.b], (tile.start + k) * 3);
  });
  colour.needsUpdate = true;
}

/** The scale an amount is drawn on: from nought to a round number at or above the most any place holds. */
export function amountDomain(unit, most) {
  const shown = display({ unit, range: [0, most], dtype: "float32" });
  const nice = niceDomain(0, (most > 0 ? most : 1) * shown.factor);
  return { shown, low: 0, high: nice.high / shown.factor, nice };
}

export const fog = {
  name: "fog",
  channels: ["colour"],
  lives_on: ["cell"],

  /**
   * context (see ./index.js). `fed.source` is the saved amount of the species in each cell;
   * `fed.extras` name, by role, the amount in each space outside ("outside") and the run's
   * ledgers of the species ("made", "cleared", "cleared outside"), where it saved them.
   */
  create({ surface, run, fed, colours }) {
    const record = run.records.get(fed.source.id);
    const extra = (role) => {
      const item = fed.extras.find((entry) => entry.role === role);
      return item ? run.records.get(item.record) || null : null;
    };
    // The spaces outside are coloured only where the picture gives them tiles of their own.
    const outside = surface.outside ? extra("outside") : null;
    const domain = amountDomain(record.unit, Math.max(record.range[1], outside ? outside.range[1] : 0));
    const ledgers = [["made", "Made here since the start"], ["cleared", "Cleared here since the start"], ["cleared outside", "Cleared here since the start"]].map(([role, label]) => ({ role, label, record: extra(role) })).filter((item) => item.record);
    const rgb = [0, 0, 0], linear = new THREE.Color();
    let { ramp, neutral } = colours;
    const species = fed.species || record.species || null;
    const written = (value, write) => `${write(value * domain.shown.factor, 3)}${domain.shown.unit ? ` ${domain.shown.unit}` : ""}`;
    return {
      record,
      outside,
      domain,
      species,
      label: species ? `Amount of ${species}` : record.label,
      update(step, valid) {
        const colourOf = (series) => (number_) => {
          if (valid && series) ramp.at(shareOf(series.at(step, number_), domain), rgb);
          else rgb.splice(0, 3, ...neutral); // no value to show
          return rgb;
        };
        paint(surface, colourOf(record), linear);
        paintOutside(surface, colourOf(outside), linear);
      },
      /** The legend's scale: the ramp from nought, with its limits in the unit shown. */
      scale(label, write) {
        const { shown, low, high, nice } = domain;
        const decimals = nice.step < 1 ? (nice.step < 0.1 ? 2 : 1) : 0;
        return { label, unit: shown.unit, gradient: ramp.css(), ticks: [low, (low + high) / 2, high].map((value, k) => ({ at: k / 2, text: write(value * shown.factor, decimals) })), marks: [] };
      },
      /** The legend's lines: what a flat tile is, and that an amount is no concentration. */
      keys() {
        const lines = [];
        if (surface.outside) {
          lines.push({ key: "tile", text: outside ? "A flat tile is a space outside the cells, coloured on the same scale by the amount in it. Where it stands is the viewer's choice: the run saves no positions" : "A flat tile is a space outside the cells. This run did not save the amount in it" });
          if (surface.outside.tiles.some((tile) => tile.held)) lines.push({ key: "tile-held", text: "A double edge: a bath held at a fixed composition" });
        }
        lines.push({ key: "amount", text: "An amount, not a concentration: places differ in volume" });
        return lines;
      },
      /** The amount in one place at a record, as text: a cell (where: "cell") or a space outside (where: "outside"). */
      reading(step, where, number_, write) {
        const series = where === "outside" ? outside : record;
        return series ? written(series.at(step, number_), write) : null;
      },
      /** The run's ledgers of the species for one place at a record: [{ label, text }], where the run saved them. */
      ledger(step, where, number_, write) {
        return ledgers
          .filter((item) => (item.role === "cleared outside") === (where === "outside"))
          .map((item) => {
            // Where the run's view gives the ledger no kind, the page does not call it a total since the start: it gives the saved number under the field's name.
            const total = item.record.kind === "cumulative";
            return { label: total ? item.label : `${item.record.label.replace(/: [^:]*$/, "")}, as saved (the run's view does not say what kind of number it is)`, text: written(item.record.at(step, number_), write), total, owner: item.record.owner || null }; // in the unit of the scale, like the amounts themselves
          });
      },
      setColours(next) {
        ({ ramp, neutral } = next);
      },
      dispose() {},
    };
  },
};
