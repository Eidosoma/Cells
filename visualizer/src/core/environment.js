// Soft surroundings for reflections, so glossy parts have highlights. A lens that wants
// them makes its own and sets it on the scene while it is active.
//
// A lost context takes with it what the card made. three.js sends again what it holds a copy
// of (geometry, pictures, programs), but the prefiltered surroundings are pictures that were
// drawn on the card, and nothing holds a copy of them: after a lost context came back, the
// page was drawn without them, about a quarter darker and without a reflection (seen on 16
// November 2026 through one of the graphics card's back ends, which loses a fresh browser's
// first context once; a phone does it to a page that was put away). So each is made again
// when the context comes back, into the same texture, which the lenses still hold.

import * as THREE from "../three.js";
import { FullScreenQuad } from "three/addons/postprocessing/Pass.js";

/** The surroundings made for each renderer: [{ target, render }], to be made again after a lost context. */
const made = new WeakMap();
let copier = null;

/** Draw one picture into another target as it is, value for value. */
function copyInto(renderer, texture, target) {
  copier ??= new FullScreenQuad(
    new THREE.ShaderMaterial({
      uniforms: { map: { value: null } },
      vertexShader: "varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }",
      fragmentShader: "uniform sampler2D map; varying vec2 vUv; void main() { gl_FragColor = texture2D(map, vUv); }",
      depthTest: false,
      depthWrite: false,
      toneMapped: false,
    })
  );
  const before = renderer.getRenderTarget(), auto = renderer.autoClear;
  copier.material.uniforms.map.value = texture;
  renderer.autoClear = true;
  renderer.setRenderTarget(target);
  copier.render(renderer);
  renderer.setRenderTarget(before);
  renderer.autoClear = auto;
  copier.material.uniforms.map.value = null;
}

/**
 * The prefiltered picture of a scene of surroundings, as a texture; `scene` makes the scene anew
 * each time it is asked. It is remembered with its renderer and made again when a lost context
 * comes back. three.js's own listener for that was added when the renderer was made, so it has
 * run, and the context is usable, by the time this one does.
 */
function prefiltered(renderer, scene, sigma) {
  const render = () => {
    const surroundings = scene();
    const generator = new THREE.PMREMGenerator(renderer);
    const target = generator.fromScene(surroundings, sigma);
    generator.dispose();
    surroundings.traverse((object) => {
      object.geometry?.dispose();
      object.material?.dispose();
    });
    return target;
  };
  const target = render();
  let list = made.get(renderer);
  if (!list) {
    made.set(renderer, (list = []));
    renderer.domElement?.addEventListener?.("webglcontextrestored", () => {
      for (const entry of list) {
        try {
          const fresh = entry.render();
          copyInto(renderer, fresh.texture, entry.target);
          fresh.dispose();
        } catch (error) {
          console.warn("the surroundings could not be made again after a lost context", error);
        }
      }
    });
  }
  list.push({ target, render });
  return target.texture;
}

/** A pale dome with two bright panels, prefiltered for reflections. Returns null if it cannot be made. */
export function makeEnvironment(renderer) {
  const surroundings = () => {
    const scene = new THREE.Scene();
    const dome = new THREE.Mesh(new THREE.SphereGeometry(60, 32, 16), new THREE.MeshBasicMaterial({ side: THREE.BackSide, vertexColors: true }));
    const position = dome.geometry.attributes.position, colours = [];
    for (let index = 0; index < position.count; index++) {
      const t = position.getY(index) / 120 + 0.5;
      colours.push(0.32 + 0.7 * t, 0.36 + 0.68 * t, 0.42 + 0.64 * t);
    }
    dome.geometry.setAttribute("color", new THREE.Float32BufferAttribute(colours, 3));
    scene.add(dome);
    for (const [x, y, z, size, power] of [[-22, 34, 26, 30, 3.0], [30, 20, -14, 20, 1.5]]) {
      const panel = new THREE.Mesh(new THREE.PlaneGeometry(size, size), new THREE.MeshBasicMaterial({ color: new THREE.Color(power, power, power), side: THREE.DoubleSide }));
      panel.position.set(x, y, z);
      panel.lookAt(0, 0, 0);
      scene.add(panel);
    }
    return scene;
  };
  try {
    return prefiltered(renderer, surroundings, 0.035);
  } catch (error) {
    console.warn("no environment map; continuing without reflections", error);
    return null;
  }
}

/**
 * A studio to reflect, for the resting look (studio reflections; core/look.js): a dim dome,
 * so that glass and wet surfaces are not washed pale by it, with four large soft lights:
 * a warm key above and to one side, a cooler one opposite, one overhead, and a low one
 * behind. The lights are large and none is small and hard, so a reflection reads as
 * shine on a surface and never as a mark. Prepared once. Returns null if it cannot be made.
 */
export function makeStudio(renderer) {
  const surroundings = () => {
    const scene = new THREE.Scene();
    const dome = new THREE.Mesh(new THREE.SphereGeometry(60, 32, 16), new THREE.MeshBasicMaterial({ side: THREE.BackSide, vertexColors: true }));
    const position = dome.geometry.attributes.position, colours = [];
    for (let index = 0; index < position.count; index++) {
      const t = position.getY(index) / 120 + 0.5;
      colours.push(0.16 + 0.44 * t, 0.19 + 0.44 * t, 0.25 + 0.45 * t);
    }
    dome.geometry.setAttribute("color", new THREE.Float32BufferAttribute(colours, 3));
    scene.add(dome);
    // Each: where it stands, how large it is, and its light (a little warm, a little cool).
    const lights = [
      [-26, 30, 24, 34, [4.6, 4.3, 3.9]],
      [34, 16, -8, 26, [1.5, 1.9, 2.7]],
      [0, 46, -6, 30, [2.2, 2.2, 2.2]],
      [-10, -8, -40, 40, [1.0, 0.85, 1.35]],
    ];
    for (const [x, y, z, size, power] of lights) {
      const panel = new THREE.Mesh(new THREE.PlaneGeometry(size, size), new THREE.MeshBasicMaterial({ color: new THREE.Color(...power), side: THREE.DoubleSide }));
      panel.position.set(x, y, z);
      panel.lookAt(0, 0, 0);
      scene.add(panel);
    }
    return scene;
  };
  try {
    return prefiltered(renderer, surroundings, 0.04);
  } catch (error) {
    console.warn("no studio to reflect; continuing with the plain surroundings", error);
    return null;
  }
}
