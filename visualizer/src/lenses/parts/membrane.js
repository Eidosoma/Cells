// The cell membrane: its glass shell, the cut edge (a band with lipid heads, or a fine line to
// scale), the charges across it, and a wall or a second membrane outside it as scenery. It
// hands on how far outside the membrane each shell stands.
//
// A part module of the cell's builder (parts/index.js), moved unchanged from buildCell in
// cell_parts.js. It draws through the lens's context, from the layout (cell_layout.js).
// It takes nothing from the layout's stream of chance.

import * as THREE from "../../three.js";
import { CUT, SPOT, beadStep, closeUpAngle, CLOSE_UP_REACH } from "../cell_layout.js";
import { instanced } from "./geometry.js";
import { solidGeometry } from "../shapes.js";
import { middle } from "../cell_scenery.js";

/** A flat strip between two open lines of as many points, facing up (geometry.js's `band` joins closed loops). */
function strip(inner, outer) {
  const count = inner.length;
  const geometry = new THREE.BufferGeometry().setFromPoints([...inner, ...outer]);
  const index = [];
  for (let q = 0; q + 1 < count; q++) index.push(q, q + 1, count + q, q + 1, count + q + 1, count + q);
  geometry.setIndex(index);
  geometry.setAttribute("normal", new THREE.Float32BufferAttribute(new Array(count * 2).fill([0, 1, 0]).flat(), 3));
  return geometry;
}

export default {
  kind: "membrane",
  draws: ["membrane"],
  build(env) {
    const { ctx, studsCtx } = env;
    const { real, style, parts, frame, outline, TOP, BASE, BEVEL, prism, inCut, edgeLine, edgeBand, taken, fine, seen, nm, envelope, membraneNm, has } = env.layout;
    const membrane = ctx.part("membrane", outline.point(4.42, 0.9, CUT + 0.3));
    const shell = new THREE.Mesh(
      prism,
      membrane.material({ hue: "bioMembrane", opacity: style.shellOpacity, side: THREE.DoubleSide, clip: true, roughness: 0.25, depthWrite: false, rim: 0.5, alphaRim: 0.5, shimmer: true })
    );
    shell.userData.pickFilter = (hit) => !inCut(hit.point);
    shell.renderOrder = 6; // after what is inside it, so it tints them like glass
    membrane.add(shell);
    // The cut edge: the membrane seen in section. Schematic: a thick band with lipid beads. To scale: a band of its own
    // thickness where that covers two pixels at the cell's stop (a bacterium's), a fine line where it does not, with the
    // line along its edges so that it never goes on a smaller screen. The close-up draws one stretch of it again, molecule
    // by molecule: that stretch of the band and its line is a piece of its own, which gives way as the camera comes to it,
    // as the dots do (cell.js, dustRange), so that the membrane is drawn once there; the rest of the cut stays whole.
    const givesWay = (material) => ((material.userData.dust = true), material);
    const closeAt = outline.reach(closeUpAngle(has)), reach = CLOSE_UP_REACH * nm;
    // The cut edge from `from` to `to` along the outline, as points `offset` out from it, about four to a unit.
    const along = (from, to, offset, y) => {
      const count = Math.max(2, Math.ceil((to - from) / 0.25));
      return Array.from({ length: count + 1 }, (_, k) => outline.spot(from + ((to - from) * k) / count, offset, y));
    };
    // The rest of the cut, and the close-up's stretch: [from, to, whether it gives way].
    const pieces = [[closeAt + reach, closeAt - reach + outline.length, false], [closeAt - reach, closeAt + reach, true]];
    const edge = (half, y, material, line, gives) =>
      pieces.map(([from, to, away]) => {
        const made = away && gives ? givesWay(material()) : material();
        return line ? new THREE.Line(new THREE.BufferGeometry().setFromPoints(along(from, to, half, y)), made) : new THREE.Mesh(strip(along(from, to, -half, y), along(from, to, half, y)), made);
      });
    if (real && seen(membraneNm)) {
      const half = (membraneNm * nm) / 2;
      membrane.add(...edge(half, CUT + 0.0003, () => membrane.material({ hue: "bioMembrane", shade: -0.22, side: THREE.DoubleSide, roughness: 0.5 }), false, true));
      membrane.add(...edge(0, CUT + 0.0002, () => membrane.lineMaterial({ hue: "bioMembrane", opacity: 1 }), true, true));
    } else if (real) membrane.add(new THREE.LineLoop(edgeLine(), membrane.lineMaterial({ hue: "bioMembrane", opacity: 1 })));
    else membrane.add(new THREE.Mesh(edgeBand(), membrane.material({ hue: "bioMembrane", shade: -0.22, side: THREE.DoubleSide, roughness: 0.5 })));
    // What stands in the cut edge is the layout's `taken`.
    if (style.beads) {
      // Counted from the channel of the close-up, so its lipid tails meet their heads.
      const heads = [];
      const step = beadStep(outline), first = outline.reach(SPOT.channels[1]);
      for (let index = 0; index < Math.round(outline.length / step); index++) {
        const s = first + index * step;
        if (taken.some(([angle, stretch]) => outline.apart(s, outline.reach(angle)) < stretch)) continue;
        heads.push({ position: outline.spot(s, 0.15, CUT + 0.06) }, { position: outline.spot(s + 0.2, -0.33, CUT + 0.06) });
      }
      membrane.add(instanced(new THREE.SphereGeometry(0.2, 12, 9), membrane.material({ hue: "bioMembrane", shade: 0.22, roughness: 0.3 }), heads));
    }
    // Charge across the membrane: plus outside, in the cleft between the cells, and minus inside.
    for (const angle of SPOT.charges) {
      studsCtx.sprite(membrane, "+", outline.point(angle, real ? 0.35 : 0.6, CUT + 0.3), style.charge);
      studsCtx.sprite(membrane, "−", outline.point(angle, real ? -0.5 : -1.15, CUT + 0.3), style.charge);
    }
    // A wall, or a second membrane, lies outside the cell membrane: scenery, drawn as clear shells.
    // Where the species gives the wall's thickness and the picture is to scale, the wall stands that far out;
    // in the schematic picture it is enlarged like the other parts, so that it can be seen.
    // A cell with two membranes and a wall has its wall between them (a bacterium with an outer membrane), so the
    // second membrane is the outermost shell. The wall was once drawn outside it, which no such cell has.
    // Each shell stands at one distance outside the cell membrane all round, as an envelope does: the cell's
    // own surface set out by that distance. It was once the cell's solid scaled about its middle, which made
    // the space between a rod's two membranes 2.5 times as wide at its ends as along its sides. The schematic
    // distances are those the shells had along the sides: a share of the cell's half-width, the picture's choice.
    // To scale, a cell whose file gives its envelope's widths (E. coli's) has each shell at its measured place, to the
    // shell's middle, and its cut drawn as a band of the shell's own thickness (cell_layout.js, envelopeOf); over the
    // close-up's stretch the band and its line give way to it, which draws the wall and the outer membrane again.
    const two = parts.membranes === 2;
    const side = frame.equator.apothem; // the cell's half-width at its widest girth
    const measured = (shell) => envelope?.[shell] && fine;
    const wallGap = !parts.wall ? 0 : measured("wall") ? envelope.wall.at * nm : parts.wall_nm !== undefined && real ? middle(parts.wall_nm) / 1000 / frame.u : side * (two ? 0.035 : 0.045);
    const outerGap = !two ? 0 : measured("outer") ? envelope.outer.at * nm : parts.wall ? Math.max(side * 0.075, wallGap + side * 0.04) : side * 0.035;
    for (const [gap, shell] of [...(parts.wall ? [[wallGap, "wall"]] : []), ...(two ? [[outerGap, "outer"]] : [])]) {
      const outer = new THREE.Mesh(solidGeometry(frame.equator.inset(-gap), TOP + gap, BASE - gap, BEVEL + gap), ctx.neutral({ opacity: 0.1, glass: 0.35, clip: true, side: THREE.DoubleSide }));
      outer.renderOrder = 7;
      ctx.illustrate(outer);
      if (measured(shell) && seen(envelope[shell].thick)) {
        const half = (envelope[shell].thick * nm) / 2;
        for (const [from, to, away] of pieces) ctx.illustrate(new THREE.Mesh(strip(along(from, to, gap - half, CUT + 0.0003), along(from, to, gap + half, CUT + 0.0003)), (away ? givesWay : (made) => made)(ctx.neutral({ opacity: shell === "wall" ? 0.38 : 0.5, side: THREE.DoubleSide }))));
      }
      if (measured(shell)) for (const [from, to, away] of pieces) ctx.illustrate(new THREE.Line(new THREE.BufferGeometry().setFromPoints(along(from, to, gap, CUT + 0.0002)), (away ? givesWay : (made) => made)(ctx.neutralLine({ opacity: 0.55 }))));
      else ctx.illustrate(new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(outline.ring(gap, CUT + 0.0002, 16)), ctx.neutralLine({ opacity: 0.55 })));
    }
    return { shells: { outerGap, wallGap } };
  },
};
