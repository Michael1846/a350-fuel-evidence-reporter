/* Offline full-flight telemetry visualization. No CDN; independent scaling per panel.
   The CSV always retains all original 5-second measurements. */
(function(){
'use strict';
const NS='http://www.w3.org/2000/svg';
const series={
 altitude_ft:{label:'Altitude',unit:'ft',color:'#137bba'},
 ias_kt:{label:'IAS',unit:'kt',color:'#2d8f67'},
 tas_kt:{label:'TAS',unit:'kt',color:'#55b092'},
 groundspeed_kt:{label:'GS',unit:'kt',color:'#b77031'},
 total_ff_kg_h:{label:'Total FF',unit:'kg/h',color:'#ba5c2e'},
 engine1_ff_kg_h:{label:'FF 1',unit:'kg/h',color:'#e0a33d'},
 engine2_ff_kg_h:{label:'FF 2',unit:'kg/h',color:'#a57a32'},
 engine1_n1_pct:{label:'Engine 1 N1',unit:'%',color:'#347bb3'},
 engine2_n1_pct:{label:'Engine 2 N1',unit:'%',color:'#4da58e'},
 fob_kg:{label:'Fuel on Board',unit:'kg',color:'#8a5dc2'},
 vertical_speed_fpm:{label:'Vertical Speed',unit:'ft/min',color:'#4968bb'},
 wind_speed_kt:{label:'Wind',unit:'kt',color:'#7c8290'}
};
const groups=[
 {label:'Altitude',keys:['altitude_ft']},
 {label:'Air speed / Ground speed',keys:['ias_kt','tas_kt','groundspeed_kt']},
 {label:'Engine fuel flow',keys:['total_ff_kg_h','engine1_ff_kg_h','engine2_ff_kg_h']},
 {label:'Engine N1',keys:['engine1_n1_pct','engine2_n1_pct']},
 {label:'Fuel on board',keys:['fob_kg']},
 {label:'Climb / Descent',keys:['vertical_speed_fpm']},
 {label:'Ambient wind speed',keys:['wind_speed_kt']}
];
let rows=[];
let active=new Set(['altitude_ft','ias_kt','groundspeed_kt','total_ff_kg_h','engine1_n1_pct','engine2_n1_pct','fob_kg','vertical_speed_fpm','wind_speed_kt']);
let lastCount=-1;
function dom(tag,attrs={},parent){const el=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,String(v));if(parent)parent.appendChild(el);return el;}
function num(v){if(v===null||v===undefined||v==='')return null;const n=Number(v);return Number.isFinite(n)?n:null;}
function fmt(n){if(n===null||n===undefined)return '—';return Math.abs(n)>=100?Math.round(n).toLocaleString('en-US'):n.toLocaleString('en-US',{maximumFractionDigits:1});}
function utc(t){return new Date(t*1000).toISOString().slice(11,19)+' UTC';}
function buildControls(){
 const container=document.getElementById('profile-series');if(!container||container.children.length)return;
 container.className='profile-toggles';
 for(const [key,cfg] of Object.entries(series)){
  const label=document.createElement('label');label.className='profile-toggle';
  const box=document.createElement('input');box.type='checkbox';box.checked=active.has(key);
  box.addEventListener('change',()=>{box.checked?active.add(key):active.delete(key);draw();});
  const sw=document.createElement('i');sw.style.background=cfg.color;label.append(box,sw,document.createTextNode(cfg.label));container.appendChild(label);
 }
}
function setData(items,count){
 rows=(items||[]).map(r=>({time:num(r.timestamp_unix),source:r})).filter(r=>r.time!==null).sort((a,b)=>a.time-b.time);
 lastCount=count??rows.length;buildControls();draw();
}
function draw(){
 const target=document.getElementById('flight-profile');if(!target)return;
 target.replaceChildren();
 const summary=document.getElementById('profile-summary');
 if(rows.length<2){target.textContent='Flight profile appears after two samples. Connect MSFS and start recording.';if(summary)summary.textContent='No flight data yet';return;}
 const W=1050,H=900,L=108,R=45,T=33,B=47,gap=13,pH=(H-T-B-gap*(groups.length-1))/groups.length;
 const x1=rows[0].time,x2=rows[rows.length-1].time;const maxTime=Math.max(1,x2-x1);
 const X=t=>L+(t-x1)/maxTime*(W-L-R);
 const svg=dom('svg',{viewBox:`0 0 ${W} ${H}`,role:'img','aria-label':'Synchronized full-flight altitude, speed, fuel flow and fuel on board charts'},target);
 svg.style.width='100%';svg.style.display='block';svg.style.background='#fcfdff';svg.style.borderRadius='10px';
 const cursor=[];
 groups.forEach((panel,p)=>{
  const ytop=T+p*(pH+gap),ybottom=ytop+pH;
  dom('rect',{x:L,y:ytop,width:W-L-R,height:pH,fill:p%2?'#f7fafd':'#f0f6fa'},svg);
  dom('text',{x:12,y:ytop+16,fill:'#385a71','font-size':12,'font-weight':'bold'},svg).textContent=panel.label;
  const keys=panel.keys.filter(k=>active.has(k));
  let all=[];for(const key of keys)for(const row of rows){const v=num(row.source[key]);if(v!==null)all.push(v);}
  if(!all.length){dom('text',{x:L+10,y:ytop+30,fill:'#8798a7','font-size':13},svg).textContent=keys.length?'No measurements':'Hidden';return;}
  let min=Math.min(...all),max=Math.max(...all);let pad=Math.max(1,(max-min)*.07);min-=pad;max+=pad;
  if(min>0&&panel.keys[0]!=='fob_kg')min=Math.max(0,min);
  const Y=v=>ybottom-7-(v-min)/(max-min)*(pH-18);
  for(let g=0;g<3;g++){let val=max-(max-min)*g/2,y=Y(val);dom('line',{x1:L,y1:y,x2:W-R,y2:y,stroke:'#dfe8ef','stroke-width':1},svg);
   dom('text',{x:L-7,y:y+4,'text-anchor':'end',fill:'#6b7f90','font-size':10},svg).textContent=fmt(val);}
  if(min<0&&max>0){const zero=Y(0);dom('line',{x1:L,y1:zero,x2:W-R,y2:zero,stroke:'#bbc9d4','stroke-dasharray':'4 4'},svg);}
  for(const key of keys){
   let chunks=[];let curr=[];
   for(const row of rows){const v=num(row.source[key]);if(v===null){if(curr.length>1)chunks.push(curr);curr=[];continue;}curr.push(`${X(row.time).toFixed(1)},${Y(v).toFixed(1)}`);}
   if(curr.length>1)chunks.push(curr);
   for(const chunk of chunks)dom('polyline',{points:chunk.join(' '),stroke:series[key].color,'stroke-width':2.1,fill:'none','stroke-linejoin':'round','stroke-linecap':'round'},svg);
  }
  const line=dom('line',{x1:L,x2:L,y1:ytop,y2:ybottom,stroke:'#526f83','stroke-width':1,'stroke-dasharray':'3 3',visibility:'hidden'},svg);cursor.push(line);
 });
 for(let i=0;i<=5;i++){
  const t=x1+i*(x2-x1)/5,x=X(t);
  dom('line',{x1:x,x2:x,y1:T,y2:H-B,stroke:'#d6e2eb','stroke-width':.8,'stroke-dasharray':'4 4'},svg);
  dom('text',{x:x,y:H-15,'text-anchor':'middle','font-size':11,fill:'#536e81'},svg).textContent=utc(t).slice(0,5);
 }
 const overlay=dom('rect',{x:L,y:T,width:W-L-R,height:H-T-B,fill:'transparent'},svg);
 const info=document.getElementById('profile-hover');
 overlay.addEventListener('mousemove',event=>{
  const box=svg.getBoundingClientRect();if(!box.width)return;
  const px=(event.clientX-box.left)*W/box.width;
  const t=x1+Math.max(0,Math.min(1,(px-L)/(W-L-R)))*(x2-x1);
  let lo=0,hi=rows.length-1;while(lo<hi){const mid=(lo+hi)>>1;if(rows[mid].time<t)lo=mid+1;else hi=mid;}
  const r=rows[Math.abs(rows[Math.max(0,lo-1)].time-t)<Math.abs(rows[lo].time-t)?Math.max(0,lo-1):lo];
  for(const line of cursor){line.setAttribute('x1',X(r.time));line.setAttribute('x2',X(r.time));line.setAttribute('visibility','visible');}
  if(info){const vals=[`<b>${utc(r.time)}</b>`];for(const [key,cfg] of Object.entries(series)){if(!active.has(key))continue;const v=num(r.source[key]);if(v!==null)vals.push(`<span><i style="background:${cfg.color}"></i> ${cfg.label}: <b>${fmt(v)} ${cfg.unit}</b></span>`);}
    info.innerHTML=vals.join('');}
 });
 overlay.addEventListener('mouseleave',()=>{for(const line of cursor)line.setAttribute('visibility','hidden');if(info)info.textContent='Hover over the chart to view all measurements at the same time.';});
 if(summary)summary.textContent=`${fmt(lastCount)} original samples · ${fmt(rows.length)} chart points · ${utc(x1)} – ${utc(x2)}. Missing data is not interpolated.`;
}
window.FlightProfile={setData,draw,getCount:()=>lastCount};
})();
