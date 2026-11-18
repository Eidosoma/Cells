// A texture painted through a 2D canvas, kept as the pixels themselves and not as the canvas.
//
// When the graphics process is lost (a driver restarts; one of the graphics card's back ends does it
// once to a fresh browser's first page), the WebGL context comes back and three.js sends every
// texture again from the picture it holds. A 2D canvas does not come back: it is blank afterwards,
// also one that was asked to stay off the card (measured, 17 November 2026: the canvas's own pixels
// read back as zero), so a texture whose picture is a canvas is sent again blank. The membranes of
// the Protein atlas lost their beads that way and showed what lies under them, the Engine view lost
// its shade and its signs, the Cell view its dots.
//
// Pixels read back once are the page's own memory. They are sent again whole, with the same
// settings a canvas takes: flipped, mipmapped, in the colour space the caller sets.
//
// Not for a texture that is painted again later: such a one keeps its canvas and paints it again
// when the context comes back (the Laws library's names, src/lenses/laws_marks.js).
import * as THREE from "../three.js";

/**
 * @param {number} width
 * @param {number} height
 * @param {(context: CanvasRenderingContext2D, canvas: HTMLCanvasElement) => void} paint
 * @returns {THREE.Texture} with the painted pixels as its picture, to be sent at its first use
 */
export function paintedTexture(width, height, paint) {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  // The pixels are read back at once, and the canvas is let go.
  const context = canvas.getContext("2d", { willReadFrequently: true });
  paint(context, canvas);
  const texture = new THREE.Texture(context.getImageData(0, 0, width, height));
  texture.needsUpdate = true;
  return texture;
}
