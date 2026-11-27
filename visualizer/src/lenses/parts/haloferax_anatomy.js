import * as THREE from "../../three.js";
import { seeded } from "./geometry.js";
import { point, sheet, turn } from "./illustration.js";

const { lerp } = THREE.MathUtils;
const coatCut = .04, lipidCut = .37, fluidCut = .57;
const tilt = Math.atan2(.38, .925);
const section = point(0,Math.sin(tilt),Math.cos(tilt));

/** Round the corners of a flattened, slightly asymmetric polygonal plate. */
function plate(v, scale = 1) {
  const angle=Math.atan2(v.z,v.x), c=Math.cos(angle), s=Math.sin(angle);
  const rounded = (Math.abs(c)**3.6+Math.abs(s)**3.6)**(-1/3.6);
  const span = Math.hypot(v.x,v.z);
  const outline=1 + span*(rounded*(1+.05*Math.sin(3*angle+.4)+.035*Math.cos(5*angle))-1);
  return point(2.04*v.x*outline+.09*v.z, .58*v.y*(1+.09*v.x), 1.56*v.z*outline).multiplyScalar(scale);
}

// Rings around the oblique section axis. All cut surfaces and their labels
// sample this same map, including both faces of the membrane's exposed rim.
function disc(h, a, r=1) {
  const spread = Math.sqrt(1-h*h)*r;
  const side = spread*Math.sin(a);
  return point(spread*Math.cos(a),h*section.y+side*section.z,h*section.z-side*section.y);
}

function rod(v) {
  // A cylindrical middle and two hemispherical ends. Latitude along x covers
  // the length, including the poles, in the same coordinates as the coat.
  const x = v.x*2.11, tip = Math.max(0,Math.abs(x)-1.47), r=Math.sqrt(Math.max(0,.64**2-tip**2));
  const radial=Math.hypot(v.y,v.z);
  return point(x,radial ? r*v.y/radial : 0,radial ? r*v.z/radial : 0);
}

function lattice(which, shape, material, cut) {
  const random=seeded(2246), placements=[];
  const sphereAt = (lat,a) => which==="rod"
    ? point(Math.sin(lat),Math.cos(lat)*Math.cos(a),Math.cos(lat)*Math.sin(a))
    : point(Math.cos(lat)*Math.cos(a),Math.sin(lat),Math.cos(lat)*Math.sin(a));
  const sample=(lat,a)=>shape(sphereAt(lat,a));
  // Use arc length on the actual body for both spacing directions. This keeps
  // the motifs legible across the broad plate face and the tight rod caps.
  let travel=0, row=0, last=sample(-Math.PI/2,0);
  for (let j=1;j<260;j++) {
    const lat=-Math.PI/2 + Math.PI*j/260, ref=sample(lat,0);
    travel+=ref.distanceTo(last);
    last=ref;
    if (travel < .159) continue;
    travel-=.159;
    const ring=Array.from({length:121},(_,i)=>sample(lat,turn*i/120));
    const lengths=[0];
    for(let k=1;k<ring.length;k++) lengths.push(lengths[k-1]+ring[k].distanceTo(ring[k-1]));
    const perimeter=lengths.at(-1), count=Math.max(1,Math.round(perimeter/.183));
    let k=1;
    for(let i=0;i<count;i++) {
      const arc=(i+.5*(row%2))*perimeter/count;
      while(k<120 && lengths[k]<arc) k++;
      const a=turn*(k-1+(arc-lengths[k-1])/(lengths[k]-lengths[k-1]))/120;
      const v=sphereAt(lat,a);
      if(cut && v.dot(section)>coatCut-.055) continue;
      const p=sample(lat,a);
      const east=sample(lat,a+.001).sub(sample(lat,a-.001)).normalize();
      const north=sample(lat+.001,a).sub(sample(lat-.001,a)).normalize();
      const n=east.clone().cross(north).normalize();
      if(n.dot(p)<0)n.negate();
      const y=n.clone().cross(east).normalize();
      placements.push({p:p.addScaledVector(n,.003), basis:new THREE.Matrix4().makeBasis(east,y,n),tone:.80+.20*random()});
    }
    row++;
  }
  // A raised, six-lobed protein motif. The pores, tilt and packing are drawn;
  // the measured six-chain assembly remains available in the Machines bench.
  const motif=sheet(18,6,(u,v)=>{
    const a=turn*u, b=turn*v, lobe=.5+.5*Math.cos(6*a);
    const thick=.019+.011*lobe, radius=.064+.007*lobe+thick*Math.cos(b);
    return point(radius*Math.cos(a),radius*Math.sin(a),.010+.018*lobe+thick*Math.sin(b));
  });
  const mesh=new THREE.InstancedMesh(motif,material,placements.length);
  const shade=new THREE.Color();
  placements.forEach(({p,basis,tone},i)=>{
    mesh.setMatrixAt(i,basis.setPosition(p));
    mesh.setColorAt(i,shade.setRGB(tone,tone,tone));
  });
  return mesh;
}

const coatLow=new THREE.Color("#903d42"), coatHigh=new THREE.Color("#d0786a");
const fluidLow=new THREE.Color("#19505d"), fluidHigh=new THREE.Color("#4e9692");
function mottling(low,high) {
  return (color,t,u,p)=>{
    const m=.43+.14*Math.sin(p.x*7+p.z*3)+.12*Math.sin(p.y*24+p.x*12)+.12*Math.cos(p.z*16-p.x*5);
    color.copy(low).lerp(high,m);
  };
}

export function buildHaloferax(put, materials) {
  const shell=(which,part,h,scale,body,paint) => {
    const shape=which==="rod" ? rod : plate;
    const geo=sheet(48,96,(t,u)=>shape(disc(Math.sin(lerp(-Math.PI/2,Math.asin(h),t)),turn*u),scale),paint);
    put(which,part,new THREE.Mesh(geo,body));
  };
  for(const which of ["plate","rod","envelope"]) {
    const cut=which==="envelope";
    if(which==="rod") {
      const body=new THREE.CapsuleGeometry(.64,2.94,16,64).rotateZ(Math.PI/2);
      const positions=body.attributes.position, colors=[], shade=new THREE.Color(), tint=mottling(coatLow,coatHigh);
      for(let i=0;i<positions.count;i++) {
        tint(shade,0,0,point().fromBufferAttribute(positions,i));
        colors.push(shade.r,shade.g,shade.b);
      }
      body.setAttribute("color",new THREE.Float32BufferAttribute(colors,3));
      put(which,"s-layer",new THREE.Mesh(body,materials.coat));
    } else {
      shell(which,"s-layer",cut ? coatCut : 1,1,materials.coat,mottling(coatLow,coatHigh));
    }
    put(which,"s-layer",lattice(which,which==="rod" ? rod : plate,materials.tile,cut));
  }
  // Offset cut planes leave a ribbon of each layer visible in a single view.
  const rim=(part,h,outer,inner,material)=>put("envelope",part,new THREE.Mesh(
    sheet(5,120,(t,u)=>plate(disc(h,turn*u),lerp(outer,inner,t))),material));
  rim("s-layer",coatCut,1,.958,materials.coatEdge);
  shell("envelope","membrane",lipidCut,.914,materials.membrane);
  rim("membrane",lipidCut,.914,.863,materials.lipidCore);
  for(const scale of [.914,.863]) {
    const curve=new THREE.CatmullRomCurve3(Array.from({length:96},(_,i)=>plate(disc(lipidCut,turn*i/96),scale)),true);
    put("envelope","membrane",new THREE.Mesh(new THREE.TubeGeometry(curve,144,.012,6,true),materials.lipidHead));
  }
  const fluidTint=mottling(fluidLow,fluidHigh);
  shell("envelope","cytoplasm",fluidCut,.835,materials.fluid,fluidTint);
  put("envelope","cytoplasm",new THREE.Mesh(sheet(26,96,(r,u)=>plate(disc(fluidCut,turn*u,r),.835),fluidTint),materials.fluid));

  const random=seeded(309800), stamp=new THREE.Object3D();
  const specks=new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1,0),materials.speck,220);
  const sites=[plate(disc(fluidCut,2.32,.58),.835)];
  for(let i=0;i<specks.count;i++) {
    const radial=Math.sqrt(random())*.97, p=plate(disc(fluidCut,random()*turn,radial),.835);
    stamp.position.copy(p).add(point(0,.004,.004));
    stamp.scale.setScalar(.008+random()*.014);
    stamp.updateMatrix();
    specks.setMatrixAt(i,stamp.matrix);
    if(i<20 && radial<.86 && sites.every(at=>at.distanceTo(p)>.15)) sites.push(p);
  }
  put("envelope","cytoplasm",specks);
  for(const [offset,radius,body] of [[0,.067,materials.largeSubunit],[.052,.046,materials.smallSubunit]]) {
    const units=new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1,1),body,sites.length);
    sites.forEach((p,i)=>{
      stamp.position.copy(p).add(point(offset*Math.cos(i),.032+offset*.4,.018+offset*Math.sin(i)));
      stamp.rotation.set(i*.43,i*.72,i*.39);
      stamp.scale.set(radius*1.2,radius*.86,radius);
      stamp.updateMatrix();
      units.setMatrixAt(i,stamp.matrix);
    });
    put("envelope","ribosome",units);
  }
  const filaments=[
    [[1.77,.39,.25],[2.08,.49,.40],[2.40,.52,.70],[2.85,.47,.73]],
    [[1.18,.47,-.44],[1.44,.61,-.80],[1.93,.76,-.95]],
    [[-1.65,.51,.21],[-1.93,.65,.34],[-2.27,.60,.61]],
  ];
  for(const coords of filaments) {
    const curve=new THREE.CatmullRomCurve3(coords.map(p=>point(...p)));
    put("rod","pilus",new THREE.Mesh(new THREE.TubeGeometry(curve,34,.018,8),materials.filament));
  }
  return {
    plate:{"s-layer":point(-.38,.55,-.27)},
    rod:{"s-layer":point(-.58,.59,.13),pilus:point(2.52,.51,.70)},
    envelope:{
      "s-layer":plate(disc(-.49,2.01),1),membrane:plate(disc(.25,.72),.914),
      cytoplasm:plate(disc(fluidCut,.24,.41),.835),ribosome:sites[0],
    },
  };
}
