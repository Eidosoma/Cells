// The protein cages and the larger machines.
//
// A part module of the cell's builder (parts/index.js), moved unchanged from buildCell in
// cell_parts.js. It draws through the lens's context, from the layout (cell_layout.js).
// It takes from the layout's one stream of chance, in the builder's fixed order.

import * as THREE from "../../three.js";
import { CUT } from "../cell_layout.js";
import { radial, instanced, dots } from "./geometry.js";

export default {
  kind: "machines",
  draws: ["cage", "machine"],
  build(env) {
    const { ctx, handles } = env;
    const { real, has, random, scatter, seat, cagesAt, machineAt, fine, nm } = env.layout;
    const assembly = has("cage") ? ctx.part("cage", cagesAt[0].clone().add(new THREE.Vector3(0, 1.25, 0))) : null;
    const machine = has("machine") ? ctx.part("machine", machineAt.clone().add(new THREE.Vector3(0, 1.2, 0))) : null;
    // To scale in a cell whose molecules are shapes at its stop, a machine is the schematic barrel at its own size, about
    // 15 nm long (a proteasome's core; the size is the picture's choice). The cage is left out of the picture for now.
    const barrelOf = (scale) => {
      const subunits = [];
      for (let index = 0; index < 4; index++) {
        const radius = (index % 3 ? 0.5 : 0.4) * scale;
        for (let one = 0; one < 7; one++) subunits.push({ position: machineAt.clone().add(new THREE.Vector3(0, (index - 1.5) * 0.36 * scale, 0)).addScaledVector(radial((one + index * 0.5) * (Math.PI * 2 / 7)), radius) });
      }
      machine.add(instanced(new THREE.SphereGeometry(0.2 * scale, 14, 10), machine.material({ hue: "bioProtein", shade: -0.12, roughness: 0.38, thin: 0.3 }), subunits));
      const barrel = new THREE.Mesh(new THREE.CylinderGeometry(0.62 * scale, 0.62 * scale, 1.4 * scale, 12), machine.proxyMaterial());
      barrel.position.copy(machineAt);
      machine.add(barrel);
    };
    if (fine) {
      if (machine) {
        barrelOf((15 * nm) / 1.48);
        machine.anchor.copy(machineAt).y += 30 * nm;
      }
    } else if (!real) {
      if (assembly) {
      const corners = new THREE.DodecahedronGeometry(0.78).attributes.position, unique = new Map(), at = new THREE.Vector3();
      for (let index = 0; index < corners.count; index++) {
        at.fromBufferAttribute(corners, index);
        unique.set(at.toArray().map((value) => value.toFixed(2)).join(), at.clone());
      }
      const subunit = assembly.material({ hue: "bioProtein", shade: 0.12, roughness: 0.3 });
      const ball = new THREE.SphereGeometry(0.3, 14, 10);
      for (const centre of [...cagesAt, seat(new THREE.Vector3(-5.5, -3.0, -3.0), 2.2), seat(new THREE.Vector3(3.0, -4.6, 2.0), 2.2)]) {
        const cluster = instanced(ball, subunit, [...unique.values()].map((position) => ({ position })));
        cluster.position.copy(centre);
        handles.cages.push(cluster);
        assembly.add(cluster);
        // Free subunits beside it: the finite pool the cage is built from.
        assembly.add(instanced(ball, subunit, [0, 1, 2].map(() => ({ position: seat(centre.clone().add(new THREE.Vector3((random() - 0.5) * 3.2, random() * 0.25, (random() - 0.5) * 3.2)), 0.95) }))));
      }
      }
      if (machine) {
      // A barrel of four rings of seven subunits, as a proteasome's core is: the outer two rings a little narrower.
      const subunits = [];
      for (let index = 0; index < 4; index++) {
        const radius = index % 3 ? 0.5 : 0.4;
        for (let one = 0; one < 7; one++) subunits.push({ position: machineAt.clone().add(new THREE.Vector3(0, (index - 1.5) * 0.36, 0)).addScaledVector(radial((one + index * 0.5) * (Math.PI * 2 / 7)), radius) });
      }
      machine.add(instanced(new THREE.SphereGeometry(0.2, 14, 10), machine.material({ hue: "bioProtein", shade: -0.12, roughness: 0.38, thin: 0.3 }), subunits));
      const barrel = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.62, 1.4, 12), machine.proxyMaterial());
      barrel.position.copy(machineAt);
      machine.add(barrel);
      }
    } else {
      // A cage is tens of nanometres across: dots at this scale.
      if (assembly) assembly.add(dots(scatter(2200), assembly.points({ hue: "bioProtein", shade: 0.12, size: 1.7, opacity: 0.85 })));
      // Larger machines are tens of nanometres across: dots at this scale.
      if (machine) {
      const ring = new THREE.Object3D(); // where their dots stand
      ring.position.copy(machineAt).setY(CUT + 0.03);
      const spot = new THREE.Mesh(new THREE.CylinderGeometry(0.7, 0.7, 0.3, 16), machine.proxyMaterial());
      spot.position.copy(ring.position);
      const few = [];
      for (let index = 0; index < 140; index++) few.push(ring.position.clone().add(new THREE.Vector3((random() - 0.5) * 1.1, (random() - 0.6) * 0.5, (random() - 0.5) * 1.1)));
      machine.add(spot, dots(few, machine.points({ hue: "bioProtein", shade: -0.12, size: 1.6, opacity: 0.8 })));
      machine.anchor.copy(ring.position).y += 0.4;
      }
      if (assembly) assembly.anchor.copy(cagesAt[0]).setY(CUT + 0.3);
    }
  },
};
