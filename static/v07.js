/* Chronological route evidence map. No 3rd-party scripts. */
let v07Overview=null;
let v07ShotId=null;
let v07Updating=false;
function v07esc(x){return String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
async function refreshRouteData(){
 if(v07Updating)return;v07Updating=true;
 try{const r=await fetch('/api/event-overview');if(!r.ok)return;v07Overview=await r.json();
     renderV07Map();renderV07Timeline();}catch(e){/* Keep UI usable without route */}
 finally{v07Updating=false;}
}
function geoXY(g,w,h){
 let b=g.bounds;if(!b)return ()=>[0,0];
 let cl=(b.lon_min+b.lon_max)/2,ca=(b.lat_min+b.lat_max)/2;
 let c=Math.max(.08,Math.cos(ca*Math.PI/180));
 let xrange=Math.max(.02,(b.lon_max-b.lon_min)*c),yrange=Math.max(.02,b.lat_max-b.lat_min);
 let fac=Math.min((w-88)/xrange,(h-84)/yrange),start=g.unwrap_center;
 return p=>{
   let unwrapped=(((((+p.lon+360)%360)-start)%360)+360)%360;
   return [w/2+(unwrapped-cl)*c*fac,h/2-(+p.lat-ca)*fac];
 };
}
function renderV07Map(){
 let target=document.getElementById('v07-route-map');if(!target||!v07Overview)return;
 const g=v07Overview.geometry||{},w=1120,h=460;
 if(!g.bounds){target.innerHTML='<div class="v07-banner">No valid GPS positions available. Import a SimBrief OFP or record GPS positions.</div>';return;}
 const xy=geoXY(g,w,h);
 const polyline=(arr,color,width=3,dash='')=>arr.length<2?'':`<polyline points="${arr.map(p=>xy(p).map(v=>v.toFixed(1)).join(',')).join(' ')}" fill="none" stroke="${color}" stroke-width="${width}" ${dash?'stroke-dasharray="'+dash+'"':''} stroke-linecap="round" stroke-linejoin="round"/>`;
 const planned=polyline(g.planned||[],'#177aaf',3.5);
 const actual=(g.actual||[]).map(seg=>polyline(seg,'#1a9a6c',3)).join('');
 const fixes=(g.planned||[]).map((p,i)=>{let [x,y]=xy(p);let show=i===0||i===g.planned.length-1||i%Math.max(1,Math.ceil(g.planned.length/12))===0;
     return `<circle cx="${x}" cy="${y}" r="3" fill="#137aaf"/>${show?`<text x="${x+5}" y="${y-7}" font-size="11" fill="#365c74">${v07esc(p.name)}</text>`:''}`}).join('');
 const density={};
 const events=(g.events||[]).map(e=>{
   const [x,y]=xy(e),k=Math.round(x/30)+'/'+Math.round(y/25),n=density[k]||0;density[k]=n+1;
   const a=x+13+n*8,b=y-14-18*n;
   return `<g class="v07-marker" role="button" tabindex="0" onclick="openV07Event('${e.label}')"><title>${v07esc(e.label+' '+e.title)}</title><circle cx="${x}" cy="${y}" r="7" fill="#c95340" stroke="white" stroke-width="2"/><path d="M${x} ${y} L${a} ${b}" stroke="#a34c3d" stroke-width="1.5"/><rect x="${a}" y="${b-14}" width="43" height="22" rx="5" fill="#ffe4db" stroke="#b05c50"/><text x="${a+5}" y="${b+2}" font-size="12" font-weight="bold" fill="#7b2c21">${e.label}</text></g>`;
 }).join('');
 let svg=`<svg class="chart" viewBox="0 0 ${w} ${h}" aria-label="Geographic route with GPS events" role="img"><rect width="${w}" height="${h}" rx="12" fill="#f6fafd"/>`;
 for(let k=1;k<=5;k++){svg+=`<path d="M${k*w/6} 30 V${h-34} M30 ${k*h/6} H${w-30}" stroke="#dae7ef" stroke-width="1"/>`;}
 target.innerHTML=svg+planned+actual+fixes+events+'</svg><div class="v07-map-legend">Blue = planned SimBrief route · Green = GPS track (gaps preserved) · Red = event location · No map tiles/API key</div>';
 document.getElementById('v07-route-note').textContent=`${(g.planned||[]).length} OFP fixes · ${(g.actual||[]).length} GPS track segments · ${(g.events||[]).length} geolocated events`;
}
function renderV07Timeline(){
 const target=document.getElementById('v07-timeline');if(!target||!v07Overview)return;
 const events=v07Overview.events||[];
 target.innerHTML=events.length?events.map(e=>{let p=e.position;
 return `<div class="evidence-timeline-entry"><b>${v07esc(e.label)}</b><div><b>${v07esc(e.title)}</b><small>${v07esc(e.utc)} · ${v07esc(e.category)} · ${p?Number(p.lat).toFixed(5)+', '+Number(p.lon).toFixed(5):'GPS unavailable'}</small><div>${v07esc((e.remark||'No remark').slice(0,400))}</div><small>${e.screenshot_count} Screenshots · ${e.fms_count} FMS values · ${e.autosave_count} BIN</small></div><button class="btn secondary" onclick="openV07Event('${e.label}')">View</button></div>`;}).join(''):'<p class="mutedtxt">No events yet. Screenshots and FMS entries will appear here in UTC order.</p>';
}
function openV07Event(label){
 const event=v07Overview?.events?.find(e=>e.label===label);if(!event)return;
 tab('evidence');
 const cards=[...document.querySelectorAll('#group-list .group-evidence')];
 const index=(appState?.groups||[]).findIndex(g=>g.id===event.raw_id);
 if(index>=0&&cards[index]){cards[index].scrollIntoView({behavior:'smooth',block:'center'});cards[index].style.boxShadow='0 0 0 3px #89c1df';setTimeout(()=>{cards[index].style.boxShadow='';},2200);return;}
 const shot=(appState?.evidence||[]).find(e=>e.id===event.raw_id);
 if(shot){openEvidenceEditor(shot.id);}else notify('Event '+label+' in the FMS log under Screenshots & FMS.',false);
}
function openEvidenceEditor(id){
 const item=(appState?.evidence||[]).find(v=>v.id===id);if(!item)return;
 v07ShotId=id;
 const d=document.getElementById('v07-shot-editor');
 document.getElementById('v07-edit-image').src='/api/image/'+encodeURIComponent(id);
 document.getElementById('v07-edit-purpose').value=item.purpose||'other';
 document.getElementById('v07-edit-phase').value=item.phase||'Other';
 document.getElementById('v07-edit-remark').value=item.note||'';
 const c=item.context||{};
 document.getElementById('v07-edit-context').textContent=`UTC: ${item.timestamp||'not verified'} · GPS: ${c.lat??'—'}, ${c.lon??'—'} · Altitude: ${c.altitude_ft??'—'} ft · FOB: ${c.fob_kg??'—'} kg · FF1/2: ${c.ff1_kg_h??'—'}/${c.ff2_kg_h??'—'} kg/h · ENG A/I 1/2: ${antiiceText(c.engine1_antiice)}/${antiiceText(c.engine2_antiice)}. Original values unchanged.`;
 if(!d.open)d.showModal();
}
function closeEvidenceEditor(){document.getElementById('v07-shot-editor').close();v07ShotId=null;}
async function saveEvidenceEditor(){if(!v07ShotId)return;
 try{const r=await api('/api/evidence-update',{id:v07ShotId,note:document.getElementById('v07-edit-remark').value,
 purpose:document.getElementById('v07-edit-purpose').value,phase:document.getElementById('v07-edit-phase').value});
 closeEvidenceEditor();setState(r.state,false);notify('Screenshot remark and category saved.');refreshRouteData();}catch(e){notify(e.message,true);}
}
// Replace legacy browser prompts, not server evidence capture.
window.editRemark=openEvidenceEditor;
window.editEvidenceTags=openEvidenceEditor;
const v07OriginalGroups=window.renderGroups;
window.renderGroups=function(state){v07OriginalGroups(state);upgradeGroupsV07(state);};
function upgradeGroupsV07(state){
 const active=document.activeElement;
 if(active&&active.closest?.('#group-list')&&['INPUT','TEXTAREA','SELECT'].includes(active.tagName))return;
 const cards=[...document.querySelectorAll('#group-list .group-evidence')];
 for(let gi=0;gi<cards.length;gi++){
   const g=state.groups[gi],card=cards[gi];if(!g)continue;
   const shots=(g.screenshot_ids||[]).map(id=>state.evidence.find(e=>e.id===id)).filter(Boolean);
   if(!card.querySelector('.group-anchor-row')){
     const wrap=document.createElement('div');wrap.className='group-anchor-row field';
     const options=`<option value="">Automatic: earliest GPS capture</option>`+
       shots.map((s,i)=>`<option value="${v07esc(s.id)}" ${g.anchor_capture_id===s.id?'selected':''}>Image ${i+1} · ${v07esc(s.timestamp||'Time unavailable')}</option>`).join('');
     wrap.innerHTML=`<label>Map marker / GPS anchor</label><select onchange="setV07Anchor('${g.id}',this.value)">${options}</select><p class="note">Position from a recorded measurement. Not shifted onto the OFP route.</p>`;
     card.querySelector('.group-items')?.before(wrap);
   }
   const nodes=[...card.querySelectorAll('.group-shot')];
   nodes.forEach((node,i)=>{let shot=shots[i];if(!shot)return;
     node.draggable=true;node.classList.add('drag-ready');
     node.addEventListener('dragstart',ev=>{ev.dataTransfer.setData('text/plain',shot.id);ev.dataTransfer.effectAllowed='move';});
     node.addEventListener('dragover',ev=>{ev.preventDefault();node.classList.add('drag-target');});
     node.addEventListener('dragleave',()=>node.classList.remove('drag-target'));
     node.addEventListener('drop',ev=>{ev.preventDefault();node.classList.remove('drag-target');let dragged=ev.dataTransfer.getData('text/plain');moveV07Image(g.id,dragged,shot.id);});
     const actions=node.querySelector('.actions');if(actions&&!actions.querySelector('.v07-edit-shot')){
       const b=document.createElement('button');b.className='btn secondary v07-edit-shot';b.textContent='Remark / Details';b.onclick=()=>openEvidenceEditor(shot.id);actions.prepend(b);}
   });
 }
}
async function setV07Anchor(id,capture_id){try{let r=await api('/api/group-anchor',{id,capture_id});setState(r.state,false);refreshRouteData();notify('GPS anchor updated.');}catch(e){notify(e.message,true)}}
async function moveV07Image(group_id,from_id,to_id){
 const g=appState?.groups?.find(x=>x.id===group_id);if(!g)return;
 let ids=g.screenshot_ids||[],a=ids.indexOf(from_id),b=ids.indexOf(to_id);
 if(a<0||b<0||a===b)return;
 const direction=a<b?1:-1;
 try{let result;for(let i=0;i<Math.abs(a-b);i++)result=await api('/api/group-move-screenshot',{group_id,screenshot_id:from_id,direction});
   if(result)setState(result.state,false);notify('Image order saved.');}catch(e){notify(e.message,true);}
}
const v07Tab=window.tab;
window.tab=function(name){v07Tab(name);if(name==='route-evidence')refreshRouteData();};
refreshRouteData();setInterval(refreshRouteData,10000);
