const root = document.getElementById('laws-atlas-choices');
const get = (id) => root.querySelector('#' + id);
// Fixed examples from the cbe54031 catalogue used by the v57 atlas.
const shelves = [
  {id:'laws', label:'Inner-model laws', families:[['Channel',11],['Cycle',15],['Route',6],['Junction',2],['Binding',1]]},
  {id:'family-laws', label:'Model-family laws', families:[['Family laws',16]]},
  {id:'kinds', label:'Kinds', families:[['Kinds',5]]},
  {id:'operators', label:'Composite operators', families:[['Split',12],['Event + split',6],['Event',4],['Process',1],['No part',2]]},
  {id:'family-operators', label:'Model-family operators', families:[['Family operators',6]]},
  {id:'design', label:'Design notes', families:[['Channel',8],['Cycle',2],['Junction',1],['Release',1],['Factor',1]]}
];
const pieces = {
  site: {name:'Site occupant replacement', family:'Event', requires:['replacement','occupancy'], writes:['site_bound_increment_fmol','site_free_increment_fmol']},
  replacement: {name:'Scheduled cell replacement', family:'Event + split', reads:['volume','extracellular_volume','membrane_area'], writes:['amount_increment','electrode_charge_transferred_C','electrode_work_pJ'], requiredBy:['site']},
  occupancy: {name:'Site occupancy', family:'Split', reads:['volume','extracellular_volume','active','outside_active','membrane_active','extracellular_amount_reference'], writes:['amount_increment','extracellular_amount_increment'], requiredBy:['site']}
};
const membership = {
  assembly: {'family-laws':[12], 'family-operators':[4]},
  composite: {laws:[11,15,6,2,1], kinds:[5], operators:[12,6,4,1,2]}
};
const verbs = {requires:'Requires', reads:'Reads', writes:'Writes', requiredBy:'Required by'};
const modelNames = ['Composite v1','Replacement v1','Tissue v3'];
const rows = [
  {name:'Site occupant replacement', membership:['direct','none','none']},
  {name:'Scheduled cell replacement', membership:['direct','direct','none']},
  {name:'Kv1.5 MH', membership:['inner','inner','direct']},
  {name:'Adenylate kinase', membership:['inner','inner','kind']}
];
const how = {direct:'Direct',inner:'Inner',kind:'Host',none:'None'};
let shelf = 'operators', model = 'library', piece = 'site', relation = 'requires', trail = [], row = 1, column = 1;
const make = (tag,className,value) => {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (value !== undefined) el.textContent = value;
  return el;
};
const svgPart = (name,attrs) => {
  const el = document.createElementNS('http://www.w3.org/2000/svg',name);
  for (const [k,v] of Object.entries(attrs)) el.setAttribute(k,String(v));
  return el;
};
const polygon = (points,fill) => svgPart('polygon',{points:points.map(p=>p.join(',')).join(' '),fill:'var(--la-'+fill+')'});
function drawPod(svg,x,y,r,height,selected,open) {
  const hex = [[0,-.58],[.87,-.29],[.87,.29],[0,.58],[-.87,.29],[-.87,-.29]];
  const base = hex.map(([dx,dy])=>[x+r*dx,y+r*dy]);
  const top = base.map(([a,b])=>[a,b-height]);
  for (const [left,right,fill] of [[1,2,'shade'],[2,3,selected?'deep':'shade'],[3,4,selected?'side':'face'],[4,5,'face']]) {
    svg.append(polygon([top[left],top[right],base[right],base[left]],fill));
  }
  svg.append(polygon(top,open?'flat':selected?'lit':'top'));
  if (open) svg.append(svgPart('polygon',{points:top.map(p=>p.join(',')).join(' '),fill:'none',stroke:'var(--la-shade)','stroke-width':1.6,'stroke-dasharray':'3 2'}));
}
function memberCount(item,i) {
  return model==='library' ? item.families[i][1] : membership[model][item.id]?.[i] || 0;
}
function shelfArt(item) {
  const svg = svgPart('svg',{viewBox:'0 0 160 66','aria-hidden':true});
  svg.append(polygon([[5,45],[118,57],[154,38],[154,42],[117,62],[5,49]],'bed-edge'));
  svg.append(polygon([[5,45],[40,25],[154,38],[118,57]],'bed'));
  const many = item.families.length > 1;
  const spots = many ? [[45,34],[78,38],[110,41],[48,47],[83,51]] : [[77,44]];
  item.families.forEach((family,i)=>{
    const [x,y] = spots[i];
    const member = model!=='library' && memberCount(item,i)>0;
    const height = 5 + family[1] * 1.09;
    drawPod(svg,x,y,many?12:19,height,member,item.id==='design');
    if (member) svg.append(svgPart('circle',{cx:x,cy:y-height,r:2.3,fill:'var(--la-deep)'}));
  });
  return svg;
}
function renderPlan() {
  const grid = root.querySelector('.la-plan-grid');
  if (!grid.children.length) {
    shelves.forEach(item=>{
      const sum = item.families.reduce((total,f)=>total+f[1],0);
      const b = make('button','la-shelf'); b.type = 'button';
      b.append(shelfArt(item),make('strong','',item.label),make('small','',sum+' pieces'));
      b.addEventListener('click',()=>{shelf = item.id; renderPlan();});
      grid.append(b);
    });
  }
  const current = shelves.find(item=>item.id===shelf);
  shelves.forEach((item,i)=>{
    const b = grid.children[i], selected = item===current;
    b.setAttribute('aria-pressed',selected);
    b.firstChild.replaceWith(shelfArt(item));
    const total=item.families.reduce((s,f)=>s+f[1],0);
    const n=item.families.reduce((s,f,j)=>s+memberCount(item,j),0);
    b.lastChild.textContent = model==='library' ? total+' pieces' : n+' of '+total+' pieces';
  });
  get('la-shelf-title').textContent = current.label+' · '+current.families.length+(current.families.length===1?' family':' families');
  root.querySelector('.la-family-list').replaceChildren(...current.families.map(([label,n],i)=>{
    const li = make('li','',label+' '); li.append(make('b','',model==='library'?n:memberCount(current,i)+'/'+n)); return li;
  }));
  get('la-model').value = model;
  get('la-plan-key').textContent = model==='library' ? 'One pod per family. Taller pods hold more pieces. Open pods mark design notes.' : 'Dots mark families the model includes. Counts show model members / total pieces.';
}
get('la-model').addEventListener('change',event=>{model=event.target.value;renderPlan();});
function fieldName(name) {
  if (get('la-field-ids').checked) return name;
  const value = name.replace(/_(fmol|C|pJ)$/,' ($1)').replaceAll('_',' ');
  return value.charAt(0).toUpperCase()+value.slice(1);
}
function putWires() {
  const lane = get('la-wire-lane'), wire = get('la-wires'), objects = get('la-objects');
  const box = lane.getBoundingClientRect();
  if (!box.width || !box.height || !objects.children.length) return;
  const left = 1, right = box.width-2, bend = .53*box.width, mid = box.height/2;
  const ys = Array.from(objects.children,el=>{const b=el.getBoundingClientRect();return b.top-box.top+b.height/2;});
  const path = (d) => svgPart('path',{d,fill:'none',stroke:'var(--la-route)','stroke-width':1.6,'stroke-linecap':'round','stroke-linejoin':'round'});
  wire.setAttribute('viewBox','0 0 '+box.width+' '+box.height);
  wire.replaceChildren(path('M '+left+' '+mid+' H '+bend),path('M '+bend+' '+Math.min(mid,...ys)+' V '+Math.max(mid,...ys)));
  ys.forEach(y=>{wire.append(path('M '+bend+' '+y+' H '+right),path('M '+(right-5)+' '+(y-3.5)+' L '+right+' '+y+' l -5 3.5'));});
}
function choosePiece(id,verb) {
  piece = id; relation = verb || Object.keys(verbs).find(k=>pieces[id][k]);
  renderTrace();
}
function renderTrace() {
  const p = pieces[piece];
  const subject = get('la-selected-pod');
  if (!subject.firstChild) {
    const svg = svgPart('svg',{viewBox:'0 0 94 68','aria-hidden':true});
    svg.append(polygon([[6,49],[63,59],[87,45],[87,49],[62,64],[6,53]],'bed-edge'),polygon([[6,49],[31,34],[87,45],[63,59]],'bed'));
    drawPod(svg,46,47,24,23,true,false); subject.append(svg);
  }
  get('la-trail').lastChild.textContent = ' '+p.family;
  get('la-piece-name').textContent = p.name+' · v1';
  get('la-wire-verb').textContent = relation==='requiredBy'?'is required by':verbs[relation].toLowerCase();
  const back = get('la-back'); back.hidden = !trail.length;
  const group = root.querySelector('.la-verbs');
  group.replaceChildren(...Object.keys(verbs).filter(k=>p[k]).map(k=>{
    const b = make('button','',verbs[k]+' · '+p[k].length);
    b.type='button'; b.setAttribute('aria-pressed',k===relation);
    b.addEventListener('click',()=>{relation=k; renderTrace(); group.querySelector('[aria-pressed="true"]').focus({preventScroll:true});});
    return b;
  }));
  const targets = get('la-objects'), otherPiece = ['requires','requiredBy'].includes(relation);
  get('la-field-setting').hidden = otherPiece;
  targets.replaceChildren(...p[relation].map(key=>{
    if (!otherPiece) return make('span','la-end',fieldName(key));
    const b = make('button','la-end'); b.type='button';
    b.append(make('span','',pieces[key].name+' · v1'),make('span','la-follow','›'));
    b.lastChild.setAttribute('aria-hidden','true');
    b.setAttribute('aria-label','Follow '+pieces[key].name+' v1');
    b.addEventListener('click',()=>{trail.push({piece,relation}); choosePiece(key); group.querySelector('[aria-pressed="true"]').focus({preventScroll:true});});
    return b;
  }));
  const count = p[relation].length;
  get('la-trace-description').textContent = otherPiece ? (relation==='requires'?'Required pieces':'Pieces requiring this operator')+' · '+count : 'Fields '+(relation==='reads'?'read':'written')+' by '+p.name+' · '+count;
  requestAnimationFrame(putWires);
}
get('la-back').addEventListener('click',()=>{
  const previous = trail.pop();
  if (!previous) return;
  choosePiece(previous.piece, previous.relation);
  root.querySelector('.la-verbs [aria-pressed="true"]').focus({preventScroll:true});
});
get('la-field-ids').addEventListener('change', renderTrace);
function cellSentence(r,c) {
  const entry = rows[r], subject = modelNames[c], object = entry.name+' v1';
  switch (entry.membership[c]) {
    case 'direct': return subject+' declares '+object+' directly.';
    case 'inner': return subject+' includes '+object+' through its inner model, Tissue v3.';
    case 'kind': return subject+' includes '+object+' through its host kind, Transporter v1.';
    default: return subject+' has no declaration for '+object+'.';
  }
}
function renderMatrix() {
  const body = root.querySelector('.la-table-wrap tbody');
  if (!body.children.length) rows.forEach((item,r)=>{
    const tr = make('tr'), heading = make('th','',item.name+' '); heading.scope='row'; heading.append(make('small','','v1')); tr.append(heading);
    item.membership.forEach((type,c)=>{
      const td=make('td'), b=make('button','la-cell'), mark=make('i','la-mark la-'+type);
      b.type='button'; b.setAttribute('aria-label',cellSentence(r,c)); mark.setAttribute('aria-hidden','true');
      b.append(mark,make('small','',how[type]));
      b.addEventListener('click',()=>{row=r;column=c;renderMatrix();});
      td.append(b); tr.append(td);
    });
    body.append(tr);
  });
  Array.from(body.rows).forEach((tr,r)=>Array.from(tr.querySelectorAll('button')).forEach((b,c)=>{
    b.setAttribute('aria-pressed',r===row && c===column); b.lastChild.hidden=!get('la-cell-labels').checked;
  }));
  get('la-cell-description').textContent = cellSentence(row,column);
}
get('la-cell-labels').addEventListener('change', renderMatrix);

const layouts = [...root.querySelectorAll('section[data-view]')];
const navigation = [...document.querySelectorAll('.view-nav a')];
function showLayout() {
  const selected = layouts.find(section => section.dataset.view === location.hash.slice(1)) || layouts[0];
  for (const section of layouts) section.hidden = section !== selected;
  for (const link of navigation) {
    if (link.hash.slice(1) === selected.dataset.view) link.setAttribute('aria-current','page');
    else link.removeAttribute('aria-current');
  }
  document.title = selected.getAttribute('aria-label') + ' · Laws design preview · Cells';
  if (selected.dataset.view === 'trace') requestAnimationFrame(putWires);
}
renderPlan();
renderTrace();
renderMatrix();
showLayout();
window.addEventListener('hashchange', showLayout);
const observer = new ResizeObserver(putWires);
observer.observe(get('la-wire-lane')); observer.observe(get('la-objects'));
