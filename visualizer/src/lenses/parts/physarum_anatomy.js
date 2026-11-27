import * as THREE from "../../three.js";
import { seeded } from "./geometry.js";
import { point, sheet, turn } from "./illustration.js";

const { lerp, smoothstep } = THREE.MathUtils;
const gold = new THREE.Color("#c27b13"), lemon = new THREE.Color("#ffe176");
const barkDark = new THREE.Color("#352f2d"), barkLight = new THREE.Color("#74685a");

// Fan coordinates run from the gathered posterior veins to the spreading margin.
// The warp is shared by the sheet and every junction placed on it.
function fanPoint(t, s) {
  const breadth = .53 + 2.54 * Math.sin(t * 1.48) ** 1.05;
  const forks =  .66*Math.sin(s * 9.6 + .8) + .34*Math.sin(s * 19 - .5) + .22*Math.cos(s * 42) + .085*Math.sin(s*69);
  const x = -4.91 + (.63*s*s+.27*Math.sin(4*s))*(1-t)**3 + 9.1*t + (.8 * forks - 1.65*s*s) * t**3
    + .18 * Math.sin(t * 11 + 3*s) * (1-t);
  const z = breadth*s + .33*Math.sin(t*6.1-.6) + .20*Math.sin(t*11 + s*4)*Math.sin(t*Math.PI);
  return point(x, .065 + .022*Math.sin(x*3.8 + z*2), z);
}

function strand(path, radius, segments, phase = 0) {
  const tangent = point(1,0,0), left = point(0,0,1), crown = point(0,1,0);
  return sheet(segments, 9, (t, u) => {
    const centre = path(t);
    tangent.copy(path(Math.min(1,t+.0005))).sub(path(Math.max(0,t-.0005))).normalize();
    left.set(-tangent.z, 0, tangent.x).normalize();
    crown.crossVectors(left, tangent).normalize();
    const angle = turn*u, r = radius(t) * (1 + .035*Math.cos(3*angle+t*12+phase));
    return centre.addScaledVector(left, r*Math.cos(angle)).addScaledVector(crown, r*.68*Math.sin(angle));
  });
}

const lanes = [-1, -.77, -.49, -.22, .01, .28, .51, .78, 1];
function lane(t, i) {
  const wander = .068*Math.sin(t*13 + i*2.1) + .035*Math.sin(t*22 + i*.8);
  return fanPoint(t, lanes[i] + wander*Math.sin(Math.PI*t));
}

function barkHeight(x, z) {
  const grain = z*10 + 2.3*Math.sin(x*1.35+z) + .54*Math.cos(x*3-z*1.8);
  return -.057 + .006*Math.sin(grain) + .004*Math.sin(2.1*grain+x);
}

export function drawNetwork(add) {
  const random = seeded(4027);
  const frontStart = s => .77 + .061*Math.cos(s*15) + .040*Math.sin(s*23) + .012*Math.sin(s*49);
  const skin = (r, v) => {
    const s = v*2-1, t = lerp(frontStart(s), 1, r);
    const p = fanPoint(t,s);
    const flutes = .5 + .5*Math.cos(s*73 + 2*Math.sin(s*12) + t*6);
    p.y += Math.sin(r*Math.PI)*(.049+.034*flutes) -.029*r;
    return p;
  };
  add("front", sheet(22, 180, skin, (color, r, v, p) => {
    const ridge = Math.cos(v*146+2*Math.sin((v*2-1)*12)+p.x*.52);
    color.copy(gold).lerp(lemon, .27+.47*r+.11*ridge+.05*Math.sin(p.x*29+p.z*38));
  }));

  // The larger routes split into several fans. Cross-veins join their neighbours
  // at the actual centre lines, then split again inside the intervening loops.
  lanes.forEach((_, i) => {
    const start = .009 + .033*(i%3), end = .91 + .046*Math.sin(i*3);
    const main = [1, 4, 7].includes(i);
    const path = u => lane(lerp(start,end,u), i);
    add(main ? "veins" : "web", strand(path, u => {
      const r = (main ? .128 : .062) * (1-.65*u) * (.91+.09*Math.sin(u*17+i));
      return r*(.13+.87*smoothstep(u,0,.10))*(1-.75*smoothstep(u,.86,1));
    }, 80, i));
    if (!i) return;
    let previous;
    for (let step = 0; step < 12; step++) {
      const a = .14 + step*.066 + .025*random(), b = a + (random()-.35)*.112;
      const bend = .08 + .19*random();
      const link = u => {
        const p = lane(a,i-1).lerp(lane(b,i),u);
        p.x += Math.sin(turn*u)*bend;
        return p;
      };
      add("web", strand(link, u => (.021+.013*Math.sin(a*9+i)**2) * (1+.26*Math.cos(u*turn)), 14));
      if (previous) {
        const tip = .28+.42*random(), base = .22+.58*random();
        const start = previous(base), end = link(tip);
        const fine = u => start.clone().lerp(end,u).add(point(0,0,.064*Math.sin(Math.PI*u+i*.2)*Math.sin(Math.PI*u)));
        add("web", strand(fine, u => .012+.007*Math.cos(Math.PI*u)**2, 12));
        if (step%2) {
          const join = fine(.45), exit = link(.90);
          add("web",strand(u=>join.clone().lerp(exit,u),()=>.009,6));
        }
      }
      previous = link;
    }
  });
  // Short raised veins disappear into the ruffled leading sheet.
  for (let i=0; i<52; i++) {
    const s = (i+.45)/52*2-1, start = frontStart(s)+.013;
    const end = .959+.035*random();
    add("web",strand(u => {
      const t=lerp(start,end,u), p=fanPoint(t,s+.018*Math.sin(Math.PI*u)*Math.cos(i));
      p.y+=.067*Math.sin(Math.PI*u)+.005;
      return p;
    }, u=>.019*(1-u)+.003, 18));
  }

  // A low, weathered specimen support provides contrast for the finest loops.
  const edge = a => 1+.034*Math.sin(a*5+.8)+.024*Math.cos(a*9)+.018*Math.sin(a*19);
  const substrate = sheet(75, 220, (r,u) => {
    const a=turn*u, reach=edge(a)*r, x=6.05*reach*Math.cos(a)-.1, z=4.35*reach*Math.sin(a);
    return point(x, barkHeight(x,z)-.24*smoothstep(r,.958,1), z);
  }, (color,r,u,p) => {
    const striation = Math.sin(p.z*14+1.65*Math.sin(p.x*1.35+p.z)+.54*Math.cos(p.x*3-p.z*1.8));
    const grain = .32 + .13*striation + .12*Math.sin(2.8*p.z+.9*p.x)+.10*random()-.15*smoothstep(r,.96,1);
    color.copy(barkDark).lerp(barkLight,grain);
  });
  const support = new THREE.Mesh(substrate, new THREE.MeshStandardMaterial({vertexColors:true, side:THREE.DoubleSide, roughness:.96}));
  support.userData.unpickable = true;
  return support;
}

export const networkAnchors = {
  veins: lane(.33,4), web: lane(.52,1), front: fanPoint(.95,.53),
};

const wallStart = Math.PI*.65, wallEnd = Math.PI*2.03;
function cross(t, angle, radius) {
  const r = radius * (1+.085*Math.cos(t*Math.PI*3.1));
  return point(t*7-3.5, Math.sin(angle)*r + .12*Math.sin(t*turn), Math.cos(angle)*r);
}

export function streamPoint(x, radial, depth) {
  const t = (x+3.5)/7;
  return point(x, -.13 + .12*Math.sin(t*turn) + depth + .025*Math.sin(1.5*x+radial), radial);
}

export function drawCutaway(add) {
  const paintWall = (color,t,u,p) => {
    const grain = .5+.5*Math.sin(p.x*21+3*Math.sin(t*14)+p.y*19+p.z*21);
    color.copy(gold).lerp(lemon,.12+.25*grain);
  };
  for (const r of [.89,1.08]) {
    add("wall",sheet(84,56,(t,u)=>cross(t,lerp(wallStart,wallEnd,u),r),paintWall));
  }
  for (const angle of [wallStart,wallEnd]) {
    add("wall",sheet(82,7,(t,u)=>cross(t,angle,lerp(.89,1.08,u)),paintWall));
  }
  for (const t of [0,1]) {
    add("wall",sheet(64,8,(u,v)=>cross(t,lerp(wallStart,wallEnd,u),lerp(.89,1.08,v)),paintWall));
  }
  // Interlacing ridges follow the curved gel wall and stop at the cut.
  for (const handed of [-1,1]) for (let i=0;i<19;i++) {
    const origin = i/20+.012, span=.065+.022*Math.sin(i);
    const path = u => cross(origin+span*u,lerp(wallStart+.035,wallEnd-.035,handed===1?u:1-u),1.086);
    const ridge = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(Array.from({length:21},(_,j)=>path(j/20))),30,.014,6);
    ridge.deleteAttribute("uv");
    add("wall",ridge.setAttribute("color",new THREE.Float32BufferAttribute(
      Array.from({length:ridge.attributes.position.count},()=>[.75,.47,.12]).flat(),3)));
  }
  // A curved exposed surface shows the volume of endoplasm inside the opened vein.
  const wetSurface = (t,u) => {
    const angle = lerp(-Math.PI*.58,Math.PI*.58,u);
    const p = streamPoint(lerp(-3.48,3.48,t), .78*Math.sin(angle), -.20+.34*Math.cos(angle));
    return p;
  };
  const deep = new THREE.Color("#216769"), light = new THREE.Color("#71b8a5");
  add("fluid",sheet(78,46,wetSurface,(color,t,u,p)=>{
    const thread=.5+.5*Math.cos(u*99+3*Math.sin(t*8)+1.2*Math.cos(t*13+u));
    color.copy(deep).lerp(light,.17+.30*thread+.11*Math.sin(p.x*.7+u*9));
  }));
  for (const t of [0,1]) {
    add("fluid",sheet(6,46,(r,u)=>{
      const p=wetSurface(t,u), centre=cross(t,0,0);
      centre.y-=.30;
      return centre.lerp(p,r);
    },color=>color.copy(deep)));
  }
}
