// Soft surroundings for reflections, so glossy parts have highlights. A lens that wants
// them makes its own and sets it on the scene while it is active.

import * as THREE from "../three.js";

/** A pale dome with two bright panels, prefiltered for reflections. Returns null if it cannot be made. */
export function makeEnvironment(renderer) {
  try {
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
    const generator = new THREE.PMREMGenerator(renderer);
    const texture = generator.fromScene(scene, 0.035).texture;
    generator.dispose();
    scene.traverse((object) => {
      object.geometry?.dispose();
      object.material?.dispose();
    });
    return texture;
  } catch (error) {
    console.warn("no environment map; continuing without reflections", error);
    return null;
  }
}
