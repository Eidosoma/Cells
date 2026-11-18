// What a protocell shows inside and round its shell (src/lenses/lineage.js, the packing "protocell"):
//
//   the catalytic network: which of the types the assembly holds speeds which, read from the run's own
//     world (its table of catalysis, `environments[].catalysis`, as the Molecules level shows it): a
//     point of light for each type held, and a lit link from a type to each type it speeds most. The
//     links are the table's standing strengths among the types held now, the strongest drawn; they
//     say nothing of which molecule helped any one join, which the run does not record. Where the
//     points stand, how many links are drawn and how they look are the picture's own.
//   the shell's glow: a soft glassy light between the protocell's two faces, so that its few lipids
//     read as one closed shell. It is the picture's own and no molecule.
//
// Instanced, one geometry each, nothing made per frame; drawn again only when what they show changes.

import * as THREE from "../three.js";

/** Links drawn inside each protocell at most, wide and on a phone; and the least factor drawn (log10 of how much a type speeds another). */
export const NETWORK = { wide: 18, narrow: 10, least: 0.5 };
const NODE_CAP = 120, LINK_CAP = 48;

/** A stable direction for a type: where its point stands inside, the picture's own. */
function placeOf(type) {
  let a = (type * 2654435761) >>> 0;
  const next = () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const z = next() * 2 - 1, phi = next() * Math.PI * 2, s = Math.sqrt(1 - z * z), depth = 0.25 + 0.7 * Math.cbrt(next());
  return [Math.cos(phi) * s * depth, z * depth * 0.8, Math.sin(phi) * s * depth];
}

/** The links of one composition: the strongest factors among the types held (row i sped by column j), at most `top`. */
export function networkOf(x, environment, top) {
  const held = [];
  for (let i = 0; i < x.length; i++) if (x[i] > 0) held.push(i);
  const links = [];
  for (const i of held) for (const j of held) {
    if (i === j) continue;
    const v = environment.catalysis(i, j);
    if (v >= NETWORK.least) links.push({ from: j, to: i, v });
  }
  links.sort((a, b) => b.v - a.v || a.from - b.from || a.to - b.to);
  return { held, links: links.slice(0, top) };
}

const GLOW_VERTEX = /* glsl */ `
varying vec3 vNormal; varying vec3 vView; varying vec3 vTint;
void main() {
  vec4 p = modelViewMatrix * instanceMatrix * vec4(position, 1.0);
  vNormal = normalize(normalMatrix * mat3(instanceMatrix) * normal);
  vView = normalize(-p.xyz);
  #ifdef USE_INSTANCING_COLOR
    vTint = instanceColor;
  #else
    vTint = vec3(1.0);
  #endif
  gl_Position = projectionMatrix * p;
}`;

const LINK_VERTEX = /* glsl */ `
varying float vAlong; varying vec3 vTint;
void main() {
  vAlong = position.y;
  #ifdef USE_INSTANCING_COLOR
    vTint = instanceColor;
  #else
    vTint = vec3(1.0);
  #endif
  gl_Position = projectionMatrix * modelViewMatrix * instanceMatrix * vec4(position, 1.0);
}`;

export class CatalyticNetwork {
  constructor(parent, { narrow = false } = {}) {
    this.top = narrow ? NETWORK.narrow : NETWORK.wide;
    this.group = new THREE.Group();
    this.group.userData.unpickable = true;
    parent.add(this.group);
    const additive = (vertexShader, fragmentShader, uniforms) => {
      const material = new THREE.ShaderMaterial({ uniforms, vertexShader, fragmentShader, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false, fog: false });
      material.userData.noContact = true;
      return material;
    };
    this.uniforms = { strength: { value: 1 } };
    this.dark = true;
    // A point of light for each type held: brightest where it faces the camera, nothing at its rim, so it reads as light and not as a molecule.
    this.nodes = new THREE.InstancedMesh(
      new THREE.IcosahedronGeometry(1, 1),
      additive(GLOW_VERTEX, `uniform float strength; varying vec3 vNormal; varying vec3 vView; varying vec3 vTint;
        void main() { float f = pow(clamp(dot(normalize(vNormal), normalize(vView)), 0.0, 1.0), 1.6); gl_FragColor = vec4(vTint * strength, f);
        #include <colorspace_fragment>
        }`, this.uniforms),
      NODE_CAP
    );
    // A link: a thin tube from the type that speeds to the type it speeds, brightening toward the second.
    this.links = new THREE.InstancedMesh(
      new THREE.CylinderGeometry(1, 1, 1, 6, 1, true).translate(0, 0.5, 0),
      additive(LINK_VERTEX, `uniform float strength; varying float vAlong; varying vec3 vTint;
        void main() { gl_FragColor = vec4(vTint * strength, 0.3 + 0.7 * vAlong);
        #include <colorspace_fragment>
        }`, this.uniforms),
      LINK_CAP
    );
    for (const mesh of [this.nodes, this.links]) {
      mesh.count = 0;
      mesh.frustumCulled = false;
      mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(mesh.instanceMatrix.count * 3), 3).setUsage(THREE.DynamicDrawUsage);
      mesh.userData.unpickable = true;
      this.group.add(mesh);
    }
    this.key = "";
    this.drawn = [];
    this.m = new THREE.Matrix4();
    this.q = new THREE.Quaternion();
    this.v = new THREE.Vector3();
    this.w = new THREE.Vector3();
    this.up = new THREE.Vector3(0, 1, 0);
    this.s = new THREE.Vector3();
    this.c = new THREE.Color();
    this.pale = new THREE.Color(0.8, 0.91, 0.93);
  }

  /**
   * groups: [{ x (counts), centre [x, y, z], room (the inside's clear radius), fade (0 to 1) }]; drawn
   * again only when `key` changes. `light(type)` gives a type's light (a THREE.Color).
   */
  draw(groups, environment, light, key) {
    if (key === this.key) return;
    this.key = key;
    const { m, q, v, w, up, c } = this;
    let nodes = 0, links = 0;
    this.drawn = [];
    for (const group of groups) {
      const { held, links: chosen } = networkOf(group.x, environment, this.top);
      this.drawn.push({ held: held.length, links: chosen });
      const keep = 1 - (group.fade || 0);
      const at = new Map();
      for (const type of held) {
        if (nodes >= NODE_CAP) break;
        const p = placeOf(type);
        const point = [0, 1, 2].map((a) => group.centre[a] + p[a] * group.room);
        at.set(type, point);
        const size = 0.035 + 0.018 * Math.sqrt(group.x[type]);
        m.compose(v.set(...point), q.identity(), w.setScalar(size));
        this.nodes.setMatrixAt(nodes, m);
        this.nodes.setColorAt(nodes, this.dark ? c.copy(light(type)).multiplyScalar(0.9 * keep) : c.copy(light(type)).lerp(this.pale, 1 - keep));
        nodes++;
      }
      const most = chosen[0]?.v ?? 1;
      for (const link of chosen) {
        if (links >= LINK_CAP) break;
        const a = at.get(link.from), b = at.get(link.to);
        if (!a || !b) continue;
        const t = most > NETWORK.least ? (link.v - NETWORK.least) / (most - NETWORK.least) : 1;
        v.set(b[0] - a[0], b[1] - a[1], b[2] - a[2]);
        const length = v.length();
        if (length < 1e-4) continue;
        q.setFromUnitVectors(up, v.normalize());
        const width = 0.008 + 0.016 * t;
        m.compose(w.set(...a), q, this.s.set(width, length, width));
        this.links.setMatrixAt(links, m);
        // Warm light in dark water; in pale water a deeper amber.
        if (this.dark) c.setRGB(1, 0.82, 0.55).multiplyScalar((0.35 + 0.65 * t) * keep);
        else c.setRGB(0.86, 0.47, 0.08).lerp(this.pale, 1 - (0.45 + 0.55 * t) * keep);
        this.links.setColorAt(links, c);
        links++;
      }
    }
    this.nodes.count = nodes;
    this.links.count = links;
    for (const mesh of [this.nodes, this.links]) {
      mesh.instanceMatrix.needsUpdate = true;
      mesh.instanceColor.needsUpdate = true;
    }
  }

  setVisible(on) {
    this.group.visible = on;
  }

  /** In pale water light adds to nothing: there the network is drawn in deeper, warmer tones laid over the water instead. */
  setTheme(dark) {
    if (this.dark === Boolean(dark)) return;
    this.dark = Boolean(dark);
    for (const mesh of [this.nodes, this.links]) {
      mesh.material.blending = dark ? THREE.AdditiveBlending : THREE.NormalBlending;
      mesh.material.needsUpdate = true;
    }
    this.uniforms.strength.value = dark ? 1 : 0.95;
    this.key = "";
  }

  dispose() {
    for (const mesh of [this.nodes, this.links]) {
      mesh.geometry.dispose();
      mesh.material.dispose();
    }
  }
}

/** The shell's two faces drawn as soft glassy surfaces, outer and inner: the picture's own, no molecule, so that a protocell's few lipids read as one closed shell. */
export class ShellGlow {
  constructor(parent, { narrow = false } = {}) {
    this.uniforms = { tint: { value: new THREE.Color() }, strength: { value: 0.5 } };
    // While two daughters overlap, each face leaves out what lies inside the other's (aOther: its centre and radius), so the two read as one shell drawn in at its waist.
    const material = new THREE.ShaderMaterial({
      uniforms: this.uniforms,
      vertexShader: `attribute vec4 aOther; varying vec4 vOther; varying vec3 vLocal;
        ${GLOW_VERTEX.replace("void main() {", "void main() {\n  vOther = aOther;\n  vLocal = (instanceMatrix * vec4(position, 1.0)).xyz;")}`,
      fragmentShader: `uniform vec3 tint; uniform float strength; varying vec3 vNormal; varying vec3 vView; varying vec3 vTint; varying vec4 vOther; varying vec3 vLocal;
        void main() { if (vOther.w > 0.0 && length(vLocal - vOther.xyz) < vOther.w) discard; float facing = abs(dot(normalize(vNormal), normalize(vView))); float rim = pow(1.0 - clamp(facing, 0.0, 1.0), 2.4); float a = (0.07 + 0.93 * rim) * strength * vTint.r; gl_FragColor = vec4(tint * (0.85 + 0.3 * rim), a);
        #include <colorspace_fragment>
        }`,
      transparent: true, depthWrite: false, side: THREE.DoubleSide, toneMapped: false, fog: false,
    });
    material.userData.noContact = true;
    const sphere = new THREE.SphereGeometry(1, narrow ? 28 : 44, narrow ? 18 : 28);
    this.other = new THREE.InstancedBufferAttribute(new Float32Array(16), 4).setUsage(THREE.DynamicDrawUsage);
    sphere.setAttribute("aOther", this.other);
    this.mesh = new THREE.InstancedMesh(sphere, material, 4);
    this.mesh.count = 0;
    this.mesh.frustumCulled = false;
    this.mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(12).fill(1), 3).setUsage(THREE.DynamicDrawUsage);
    this.mesh.userData.unpickable = true;
    this.mesh.renderOrder = 3;
    parent.add(this.mesh);
    this.m = new THREE.Matrix4();
    this.q = new THREE.Quaternion();
    this.v = new THREE.Vector3();
    this.s = new THREE.Vector3();
    this.c = new THREE.Color();
  }

  /** shells: [{ centre, outer, inner, fade }]: each a protocell's two faces. */
  draw(shells) {
    let n = 0;
    const two = shells.slice(0, 2);
    two.forEach((shell, index) => {
      const other = two[1 - index];
      for (const [face, share] of [["outer", 1], ["inner", 0.7]]) {
        const radius = Math.max(0.1, shell[face]);
        this.m.compose(this.v.set(...shell.centre), this.q.identity(), this.s.setScalar(radius));
        this.mesh.setMatrixAt(n, this.m);
        this.mesh.setColorAt(n, this.c.setScalar(share * (1 - (shell.fade || 0))));
        if (other) this.other.setXYZW(n, other.centre[0], other.centre[1], other.centre[2], Math.max(0.1, other[face]));
        else this.other.setXYZW(n, 0, 0, 0, 0);
        n++;
      }
    });
    this.mesh.count = n;
    this.mesh.instanceMatrix.needsUpdate = true;
    this.mesh.instanceColor.needsUpdate = true;
    this.other.needsUpdate = true;
  }

  setTint(colour, dark) {
    this.uniforms.tint.value.set(colour);
    this.uniforms.strength.value = dark ? 0.55 : 0.7;
  }

  dispose() {
    this.mesh.geometry.dispose();
    this.mesh.material.dispose();
  }
}
