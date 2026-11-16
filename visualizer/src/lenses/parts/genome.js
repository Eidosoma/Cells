// Gene regulation coupled to tissue: a network round the nucleus or the free chromosome.
//
// A part module of the cell's builder (parts/index.js), moved unchanged from buildCell in
// cell_parts.js. It draws through the lens's context, from the layout (cell_layout.js).
// It takes nothing from the layout's stream of chance.

import * as THREE from "../../three.js";
import { instanced } from "./geometry.js";

export default {
  kind: "genome",
  draws: ["genome"],
  build(env) {
    const { ctx } = env;
    const { real, has, coreAt, coreRadius } = env.layout;
    // Gene regulation coupled to tissue is planned: a network round the nucleus, its knots and threads in the
    // nucleus's own colour (with "Colour: Status" a sketch, as every planned part is).
    if (has("genome")) {
    const genome = ctx.part("genome", coreAt.clone().add(new THREE.Vector3(coreRadius + 0.3, 1.5, 1.9)));
    const net = new THREE.IcosahedronGeometry(coreRadius + 0.6, 1);
    const cage = new THREE.LineSegments(new THREE.EdgesGeometry(net, 1), genome.lineMaterial({ hue: "bioNucleus", opacity: 0.3 }));
    cage.position.copy(coreAt);
    const knots = [], seen = new Set(), corner = new THREE.Vector3();
    for (let index = 0; index < net.attributes.position.count; index++) {
      corner.fromBufferAttribute(net.attributes.position, index);
      const key = corner.toArray().map((value) => value.toFixed(2)).join();
      if (!seen.has(key)) {
        seen.add(key);
        knots.push({ position: corner.clone().add(coreAt) });
      }
    }
    const body = new THREE.Mesh(net, genome.proxyMaterial());
    body.position.copy(coreAt);
    // A network is mostly open space: a click goes through it to what is solid within, and chooses it only where nothing is.
    const nodes = instanced(new THREE.SphereGeometry(real ? 0.06 : 0.1, 10, 8), genome.material({ hue: "bioNucleus", shade: 0.3, roughness: 0.35, emissive: 0.08 }), knots);
    cage.userData.seeThrough = body.userData.seeThrough = nodes.userData.seeThrough = true;
    genome.add(cage, body, nodes);
    }
  },
};
