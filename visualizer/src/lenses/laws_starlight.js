import * as THREE from "../three.js";

// The backdrop has no stars. Every point of light above it comes from the catalogue or a selected route.
const skyVertex = `
  varying vec2 sky;
  void main() { sky = position.xy; gl_Position = vec4(sky, 0.999, 1.0); }
`;
const skyFragment = `
  varying vec2 sky;
  uniform vec2 orbit;
  float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f);
    return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+1.0),f.x),f.y);
  }
  void main() {
    vec2 p = sky + orbit;
    float mist = .52*noise(3.6*p) + .3*noise(8.4*p+.8) + .18*noise(17.0*p);
    float band = p.y - .33*p.x + .65*(mist-.5);
    float dust = exp(-5.0*band*band)*mist;
    vec3 hue = mix(vec3(.025,.18,.22),vec3(.15,.11,.255),smoothstep(-.5,.9,p.x));
    vec3 light = vec3(.018,.035,.067) + hue*dust + vec3(.018,.04,.056)*exp(-1.8*dot(p,p));
    gl_FragColor = vec4(light,1.);
  }
`;
const glowVertex = `
  attribute float radius;
  attribute float sweepAt;
  uniform float focal;
  uniform float pixelRatio;
  uniform float sweep;
  varying vec3 tint;
  varying float flash;
  void main() {
    vec4 eye = modelViewMatrix * vec4(position,1.);
    flash = 1.-smoothstep(0.,.16,abs(sweep-sweepAt));
    tint = color;
    gl_PointSize = clamp(radius*focal/max(.1,-eye.z),3.*pixelRatio,96.*pixelRatio) * (1.+.4*flash);
    gl_Position = projectionMatrix*eye;
  }
`;
const glowFragment = `
  varying vec3 tint;
  varying float flash;
  void main() {
    float r = length(gl_PointCoord-.5)*2.;
    if (r>=1.) discard;
    float halo = .38*exp(-5.*r*r) + .62*exp(-37.*r*r);
    gl_FragColor = vec4(tint*(1.+flash*.6),halo*(1.-smoothstep(.78,1.,r)));
    #include <colorspace_fragment>
  }
`;

function lightGeometry(positions, colours, radii, phases) {
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  g.setAttribute("color", new THREE.Float32BufferAttribute(colours, 3));
  if (radii) {
    g.setAttribute("radius", new THREE.Float32BufferAttribute(radii, 1));
    g.setAttribute("sweepAt", new THREE.Float32BufferAttribute(phases, 1));
  }
  return g;
}

export class StarLight {
  constructor() {
    this.root = new THREE.Group();
    this.root.userData.unpickable = true;
    this.sky = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.ShaderMaterial({
      uniforms: { orbit: { value: new THREE.Vector2() } }, vertexShader: skyVertex, fragmentShader: skyFragment,
      depthTest: false, depthWrite: false, toneMapped: false,
    }));
    this.sky.frustumCulled = false;
    this.sky.renderOrder = -1000;
    this.glow = new THREE.ShaderMaterial({
      uniforms: { focal: { value: 800 }, pixelRatio: { value: 1 }, sweep: { value: -3 } },
      vertexShader: glowVertex, fragmentShader: glowFragment, vertexColors: true,
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false,
    });
    this.stars = new THREE.Points(new THREE.BufferGeometry(), this.glow);
    this.lines = new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ vertexColors: true, toneMapped: false }));
    this.pulse = new THREE.Points(lightGeometry([0, 0, 0], [1, .98, .8], [1.5], [-10]), this.glow);
    this.pulse.visible = false;
    this.root.add(this.sky, this.lines, this.stars, this.pulse);
    this.colour = new THREE.Color();
    this.reset();
  }
  reset() {
    this.positions = []; this.colours = []; this.radii = []; this.phases = [];
    this.lineEnds = []; this.lineColours = [];
  }
  star(point, colour, radius, phase = -10) {
    this.positions.push(point.x, point.y, point.z);
    this.colour.set(colour).toArray(this.colours, this.colours.length);
    this.radii.push(radius); this.phases.push(phase);
  }
  line(a, b, colour) {
    this.lineEnds.push(a.x, a.y, a.z, b.x, b.y, b.z);
    this.colour.set(colour).toArray(this.lineColours, this.lineColours.length);
    this.colour.toArray(this.lineColours, this.lineColours.length);
  }
  ring(at, radius, colour, start = 0, end = Math.PI * 2, tilt = 0) {
    const steps = Math.max(3, Math.ceil((end - start) * 10));
    let last;
    for (let i = 0; i <= steps; i++) {
      const a = start + (end - start) * i / steps;
      const sin = radius * Math.sin(a);
      const p = new THREE.Vector3(at.x + radius * Math.cos(a), at.y + sin * Math.sin(tilt), at.z + sin * Math.cos(tilt));
      if (last) this.line(last, p, colour);
      last = p;
    }
  }
  finish() {
    this.stars.geometry.dispose();
    this.lines.geometry.dispose();
    this.stars.geometry = lightGeometry(this.positions, this.colours, this.radii, this.phases);
    this.lines.geometry = lightGeometry(this.lineEnds, this.lineColours);
  }
  update(stage) {
    const ratio = stage.renderer.getPixelRatio();
    this.glow.uniforms.focal.value = stage.height * ratio / (2 * Math.tan(THREE.MathUtils.degToRad(stage.camera.fov) / 2));
    this.glow.uniforms.pixelRatio.value = ratio;
    this.sky.material.uniforms.orbit.value.set(.16 * Math.sin(stage.rig.azimuth), .16 * Math.cos(stage.rig.polar));
  }
  dispose() {
    for (const item of this.root.children) item.geometry.dispose();
    this.sky.material.dispose(); this.lines.material.dispose(); this.glow.dispose();
  }
}
