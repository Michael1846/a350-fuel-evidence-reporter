#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Offline iniBuilds A350 Fuel Evidence Reporter. Python 3.10+, stdlib server.
Requires reportlab, PyMuPDF, Pillow. Binds only to 127.0.0.1.
"""
import base64, csv, datetime as dt, io, json, math, os, re, secrets, socket, sys, zipfile, time, webbrowser
from copy import deepcopy
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from threading import RLock
from simbrief_client import fetch_latest, download_pdf
from simbridge import Bridge
from aircraft_engine_adapter import load_profile,save_profile
from lvar_source_scan import scan as scan_lvars
from telemetry_store import TelemetryStore,FIELDS
from evidence_checklist import checklist, ISSUE_TYPES
from evidence_groups import (new_group, get_group, ensure_group, assign_screenshot,
                             reorder_screenshot, ordered_screenshots, evidence_audit)
from urllib.parse import urlparse
from PIL import Image, ImageOps
from evidence_capture import freeze_sim_context, grab_screen, GlobalCaptureHotkey
from screen_target import target_status
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table,
                                TableStyle, Image as RLImage, PageBreak, KeepTogether)
import fitz
from xml.sax.saxutils import escape as xml_escape
from event_timeline import event_list,event_summary
from route_map import geometry
from report_v07 import make_report as make_report_v07
from runtime_paths import data_directory

APP_VERSION = '0.7.11-rc2'
BASE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
DATA = data_directory()
FILES = DATA / 'files'
TELEM_PATH = DATA / 'flight_telemetry_5s.csv'
TELEM_STORE = TelemetryStore(TELEM_PATH)
STATE_PATH = DATA / 'case.json'
CONFIG_PATH = DATA / 'config.json'
ENGINE_PROFILE_PATH = DATA / 'engine_sources.json'
LOCK = RLock()
PORT = int(os.environ.get('A350_REPORTER_PORT', '8087'))

DEF = {
  'meta': {'flight':'', 'date':'', 'dep':'', 'arr':'', 'sim':'MSFS 2024',
           'variant':'A350-900', 'cabin':'No Cabin', 'version':'',
           'aircraft_title':'','version_source':'',
           'live_time':'', 'live_weather':'', 'ofp_trip_kg':'',
           'ofp_block_kg':'', 'ofp_takeoff_kg':'', 'ofp_dest_efob_kg':'',
           'fuel_bias_pct':'', 'cost_index':'', 'notes':'',
           'redact_terms':''},
  'flight_id': '', 'samples': [], 'snapshots': [], 'evidence': [], 'ofp': None, 'bin': None, 'autosaves': [], 'groups': [],
  'case_types':list(ISSUE_TYPES),'active_capture_group_id':'','first_airborne_utc_unix':None,
  'route_fixes': [], 'skipped_waypoints':[], 'telemetry': [], 'tracking_enabled': False, 'simbrief_user_id': '', 'markers': []
}

def ensure():
    DATA.mkdir(parents=True,exist_ok=True); FILES.mkdir(parents=True,exist_ok=True)
    if not STATE_PATH.exists(): save(deepcopy(DEF))
    if not CONFIG_PATH.exists(): CONFIG_PATH.write_text(json.dumps({'token':secrets.token_hex(16)}), encoding='utf-8')

def load():
    ensure()
    with LOCK:
        state=json.loads(STATE_PATH.read_text(encoding='utf-8'))
        # v0.5 compatibility; never discard a previously imported autosave.
        if not state.get('flight_id'):
            state['flight_id']=secrets.token_hex(12)
            save(state)
        state.setdefault('groups',[])
        state.setdefault('autosaves',[])
        state.setdefault('active_capture_group_id','')
        if state.get('bin') and not any(b.get('id')==state['bin'].get('id') for b in state['autosaves']):
            old=dict(state['bin']);old.setdefault('group_id','');state['autosaves'].append(old)
        for group in state['groups']: group.setdefault('screenshot_ids',[])
        return state

def save(data):
    DATA.mkdir(parents=True,exist_ok=True)
    with LOCK:
        tmp = STATE_PATH.with_suffix('.tmp'); tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8'); tmp.replace(STATE_PATH)

def number(v):
    try:
        f=float(v)
        if not (-1e10 < f < 1e10): return None
        return round(f, 3)
    except (ValueError,TypeError): return None

def safe_str(v, maxlen=200): return re.sub(r'[\x00-\x1f<>]', ' ', str(v or ''))[:maxlen]

def sample_from(raw):
    r = {
        'ident':safe_str(raw.get('ident',''), 35),
        'timestamp':number(raw.get('checked_at',raw.get('timestamp'))),
        'actual_kg':number(raw.get('actual_fob_kg',raw.get('actual_kg'))),
        'planned_kg':number(raw.get('planned_fob_kg',raw.get('planned_kg'))),
        'distance_nm':number(raw.get('gps_distance_nm',raw.get('distance_nm'))),
        'waypoint_idx':number(raw.get('waypoint_idx')),
        'check_type':safe_str(raw.get('check_type','WAYPOINT'),40),
        'source':safe_str(raw.get('source','import'),30),
    }
    if not r['ident'] or r['timestamp'] is None or r['actual_kg'] is None: raise ValueError('Checkpoint requires ident, timestamp, actual_kg')
    r['delta_kg']=round(r['actual_kg']-r['planned_kg'],3) if r['planned_kg'] is not None else None
    return r

def ingest_csv(text):
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    headers=set(reader.fieldnames or [])
    if 'ident' not in headers or ('actual_fob_kg' not in headers and 'actual_kg' not in headers):
        raise ValueError('CSV must include ident and actual_fob_kg (or actual_kg)')
    rows=[]
    for raw in reader:
        if not any(str(x).strip() for x in raw.values() if x is not None): continue
        rows.append(sample_from(raw))
    if not rows: raise ValueError('No valid checkpoint rows')
    if len(rows)>20000: raise ValueError('Too many samples')
    return rows

def merge_samples(state, rows):
    existing={(v['ident'],v.get('timestamp')):v for v in state['samples']}
    for r in rows: existing[(r['ident'],r.get('timestamp'))]=r
    state['samples']=sorted(existing.values(),key=lambda v:v['timestamp'] or 0)

def file_for(item):
    if not item:return None
    path = FILES / item['id']
    return path if path.is_file() else None

def upload(name, data64, category='', phase='', timestamp='', note='', purpose='', observation_id='', group_id=''):
    if len(data64)>150_000_000:raise ValueError('Attachment too large')
    raw=base64.b64decode(data64,validate=True)
    if len(raw)>100*1024*1024:raise ValueError('Max attachment size is 100 MB')
    suffix=Path(name).suffix.lower()
    if category=='screenshot':
        if suffix not in ('.png','.jpg','.jpeg','.webp'):raise ValueError('Use PNG, JPG or WebP for screenshots')
        try:
            im=Image.open(io.BytesIO(raw));im.verify()
            im=Image.open(io.BytesIO(raw));im=ImageOps.exif_transpose(im)
            # Full-size, readable FMS digits are evidence. Do not downscale the capture.
            if im.width*im.height>70_000_000:raise ValueError('Screenshot resolution exceeds 70 megapixels')
            out=io.BytesIO();im.convert('RGB').save(out,'PNG',optimize=True);raw=out.getvalue()
        except Exception as e:raise ValueError('Invalid image: '+str(e))
        suffix='.png'
    elif category=='ofp':
        if suffix!='.pdf' or not raw.startswith(b'%PDF'):raise ValueError('An OFP must be a PDF')
        try:fitz.open(stream=raw,filetype='pdf').close()
        except Exception as e:raise ValueError('Invalid PDF: '+str(e))
    elif category=='bin':
        if suffix!='.bin':raise ValueError('Use OIS .bin files')
    else:raise ValueError('Invalid attachment type')
    ident=secrets.token_hex(14)+suffix
    (FILES/ident).write_bytes(raw)
    return {'id':ident,'original':safe_str(name,100),'category':category,
            'phase':safe_str(phase,80),'timestamp':safe_str(timestamp,40),
            'note':safe_str(note,350),'purpose':safe_str(purpose,60),
            'observation_id':safe_str(observation_id,40), 'group_id':safe_str(group_id,40), 'bytes':len(raw)}

def redact_pdf(raw, terms):
    src=fitz.open(stream=raw,filetype='pdf')
    terms=[s.strip() for s in re.split(r'[,;\n]',terms or '') if s.strip()]
    # Remove both full-name variants and configured substrings; do not silently claim all PII is gone.
    count=0
    for page in src:
        for term in terms:
            for rect in page.search_for(term):
                page.add_redact_annot(rect,fill=(0,0,0));count+=1
        if page.annots(): page.apply_redactions()
    src.set_metadata({})
    data=src.tobytes(garbage=4,deflate=True,clean=True)
    src.close()
    return data,count

def fmt_utc(timestamp):
    try:return dt.datetime.fromtimestamp(float(timestamp),dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    except Exception:return '—'

def fkg(val):return (f'{val:,.1f} kg' if isinstance(val,(int,float)) else '—')
def printable(v):return safe_str(v,350) or '—'

def graph_pil(samples):
    from PIL import ImageDraw, ImageFont
    w,h=1200,365
    im=Image.new('RGB',(w,h),'white');d=ImageDraw.Draw(im)
    left,right,top,bottom=90,w-35,35,h-65
    actual=[x['actual_kg'] for x in samples]
    plan=[x['planned_kg'] for x in samples if x['planned_kg'] is not None]
    values=actual+plan
    if not values:return None
    vmin=min(values);vmax=max(values);pad=max(100,(vmax-vmin)*.13);vmin-=pad;vmax+=pad
    n=len(samples)
    xy=lambda i,v: (left + ((right-left)*i/max(1,n-1)),top+(bottom-top)*(vmax-v)/(vmax-vmin))
    for k in range(5):
        y=top+(bottom-top)*k/4;d.line([(left,y),(right,y)],fill='#e4e9f0',width=2)
        d.text((3,y-10),f'{vmax-(vmax-vmin)*k/4:,.0f} kg',fill='#506277')
    d.line([(left,top),(left,bottom),(right,bottom)], fill='#9ba6b7',width=2)
    d.line([xy(i,v) for i,v in enumerate(actual)],fill='#0f7fcb',width=5,joint='curve')
    for i,v in enumerate(actual):
        x,y=xy(i,v);d.ellipse((x-4,y-4,x+4,y+4),fill='#0f7fcb')
    prev=[]
    for i,x in enumerate(samples):
        if x['planned_kg'] is None:
            if len(prev)>1:d.line(prev,fill='#e69e30',width=4)
            prev=[];continue
        prev.append(xy(i,x['planned_kg']))
    if len(prev)>1:d.line(prev,fill='#e69e30',width=4)
    ticks=sorted(set([0, max(0,n//4),max(0,n//2),max(0,3*n//4),n-1]))
    for i in ticks:
        x,y=xy(i,vmin);d.text((x-12,bottom+10),samples[i]['ident'][:8],fill='#526273')
    d.line([(left,15),(left+32,15)],fill='#0f7fcb',width=5);d.text((left+40,7),'Recorded FOB',fill='#34435a')
    d.line([(left+280,15),(left+312,15)],fill='#e69e30',width=4);d.text((left+320,7),'Reference FOB',fill='#34435a')
    b=io.BytesIO();im.save(b,format='PNG');return b.getvalue()

def telemetry_trend_png(records):
    """Full-flight aligned axes: altitude, speed, engine FF, FOB, VS, wind.

    The actual UTC time coordinate is used, not the sample index. Segments are
    interrupted for missing values and data gaps; no values are invented.
    """
    from PIL import ImageDraw
    if len(records)<2:return None
    panels=[('Altitude (ft)',['altitude_ft'],['#137bba']),
            ('IAS / ground speed (kt)',['ias_kt','groundspeed_kt'],['#2d8f67','#b77031']),
            ('Fuel flow (kg/h)',['total_ff_kg_h'],['#ba5c2e']),
            ('Engine N1 (%)',['engine1_n1_pct','engine2_n1_pct'],['#347bb3','#4da58e']),
            ('Fuel on board (kg)',['fob_kg'],['#8a5dc2']),
            ('Vertical speed (ft/min)',['vertical_speed_fpm'],['#4968bb']),
            ('Wind speed (kt)',['wind_speed_kt'],['#7c8290'])]
    w,h=1200,1030
    im=Image.new('RGB',(w,h),'white');draw=ImageDraw.Draw(im)
    left,right,top,bottom=185,w-45,46,h-46
    gap=13;panel_h=(bottom-top-gap*(len(panels)-1))/len(panels)
    try:
        times=[float(r['timestamp_unix']) for r in records]
    except (ValueError,TypeError,KeyError):return None
    start,end=times[0],times[-1]
    if end<=start:return None
    draw.text((left,12),'Aligned flight profile | continuous telemetry',fill='#254866')
    get=lambda row,key: (float(row[key]) if row.get(key) not in (None,'') and math.isfinite(float(row[key])) else None)
    for p,(label,keys,colors_) in enumerate(panels):
        yt=top+p*(panel_h+gap);yb=yt+panel_h
        draw.rectangle((left,yt,right,yb),outline='#d5e0e8',width=2)
        draw.text((12,yt+8),label,fill='#415a6b')
        pairs=[]
        for key in keys:
            for r in records:
                try:v=get(r,key)
                except (ValueError,TypeError):v=None
                if v is not None:pairs.append(v)
        if not pairs:continue
        vmin,vmax=min(pairs),max(pairs)
        margin=max((vmax-vmin)*.08,1)
        vmin-=margin;vmax+=margin
        draw.text((12,yt+30),f'{vmax:,.0f} max',fill='#617286')
        draw.text((12,yb-17),f'{vmin:,.0f} min',fill='#617286')
        if vmin<0<vmax:
            zy=yb-((0-vmin)/(vmax-vmin))*(yb-yt)
            draw.line((left,zy,right,zy),fill='#c8d6e1',width=1)
        for key,color in zip(keys,colors_):
            prior=None;prior_t=None
            for row,t in zip(records,times):
                try:v=get(row,key)
                except (ValueError,TypeError):v=None
                if v is None:prior=None;prior_t=None;continue
                x=left+((t-start)/(end-start))*(right-left)
                y=yb-((v-vmin)/(vmax-vmin))*(yb-yt)
                if prior and prior_t is not None and t-prior_t <= 12:
                    draw.line((prior,(x,y)),fill=color,width=3)
                prior=(x,y);prior_t=t
        if keys==['ias_kt','groundspeed_kt']:
            draw.text((right-220,yt+5),'IAS: green  GS: orange',fill='#657287')
        elif keys==['engine1_n1_pct','engine2_n1_pct']:
            draw.text((right-240,yt+5),'N1 1: blue  N1 2: green',fill='#657287')
    for i in range(6):
        x=left+(right-left)*i/5
        draw.line((x,top,x,bottom),fill='#d9e5ee',width=1)
        t=start+(end-start)*i/5
        draw.text((x-30,h-30),dt.datetime.fromtimestamp(t,dt.timezone.utc).strftime('%H:%M'),fill='#536b7f')
    out=io.BytesIO();im.save(out,format='PNG');return out.getvalue()

class NumberedDoc(BaseDocTemplate):
    def __init__(self,bio,**kwargs):
        super().__init__(bio, pagesize=A4, leftMargin=42,rightMargin=42,topMargin=48,bottomMargin=45,**kwargs)
        frame=Frame(self.leftMargin,self.bottomMargin,self.width,self.height, leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
        self.addPageTemplates(PageTemplate(id='Normal',frames=frame,onPage=self.decor))
    def decor(self,canvas,doc):
        canvas.setStrokeColor(colors.HexColor('#ccd7e0'));canvas.line(42,31,A4[0]-42,31)
        canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#536378'))
        canvas.drawString(42,21,'A350 FUEL EVIDENCE REPORT | MEASURED DATA')
        canvas.drawRightString(A4[0]-42,21,f'Page {doc.page}')

def make_report_legacy(state):
    sty=getSampleStyleSheet();sty.add(ParagraphStyle(name='MainTitle2',parent=sty['Title'],fontName='Helvetica-Bold',fontSize=18,leading=22,textColor=colors.HexColor('#102b45'),spaceAfter=10))
    sty.add(ParagraphStyle(name='Section2',parent=sty['Heading2'],fontSize=11,leading=14,textColor=colors.HexColor('#102b45'),spaceBefore=10,spaceAfter=6))
    sty.add(ParagraphStyle(name='Small2',parent=sty['Normal'],fontSize=8,leading=11,textColor=colors.HexColor('#38485c')))
    sty.add(ParagraphStyle(name='Tiny2',parent=sty['Normal'],fontSize=7,leading=9,textColor=colors.HexColor('#38485c')))
    m=state['meta'];S=[]
    wf=checklist(state,TELEM_STORE.count)
    S.append(Paragraph('A350 Fuel Evidence Report',sty['MainTitle2']))
    S.append(Paragraph('Recorded flight and evidence data',sty['Small2']));S.append(Spacer(1,10))
    S.append(Paragraph('Reported issue categories',sty['Section2']))
    for item in wf['issues']:
        S.append(Paragraph('&#8226; '+item['title'].replace('&','&amp;'),sty['Small2']))
    info=[('Date',m.get('date','')),('Flight',m.get('flight','')),('Route',str(m.get('dep',''))+' → '+str(m.get('arr',''))),
          ('Simulator',m.get('sim','')),('Aircraft',str(m.get('variant',''))+' / '+str(m.get('cabin',''))),('Aircraft version',m.get('version','')),('Version source',m.get('version_source','')),
          ('Live Time',m.get('live_time','')),('Live Weather',m.get('live_weather',''))]
    fuel=[('Block fuel',m.get('ofp_block_kg','')),('Takeoff fuel',m.get('ofp_takeoff_kg','')),('Trip fuel',m.get('ofp_trip_kg','')),
          ('SimBrief Dest EFOB',m.get('ofp_dest_efob_kg','')),('Fuel bias (%)',m.get('fuel_bias_pct','')),('Cost Index',m.get('cost_index',''))]
    def table_for(pairs):
        data=[[Paragraph(str(k),sty['Small2']), Paragraph(printable(v),sty['Small2'])] for k,v in pairs]
        t=Table(data,colWidths=[144,360],hAlign='LEFT');t.setStyle(TableStyle([('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#dce3ea')),('ROWBACKGROUNDS',(0,0),(-1,-1),[colors.white,colors.HexColor('#f5f8fa')]),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]));return t
    S.append(Paragraph('Flight configuration',sty['Section2']));S.append(table_for(info))
    S.append(Paragraph('OFP baseline',sty['Section2']));S.append(table_for(fuel))
    S.append(Paragraph('Evidence checklist',sty['Section2']))
    for group in wf['stages']:
        req=[it for it in group['items'] if it['required']]
        if not req:continue
        S.append(Paragraph(group['title'].split('·',1)[-1].strip(),sty['Small2']))
        S.append(table_for([(it['title'],'Available' if it['done'] else 'Not recorded') for it in req]))
    rows=state['samples'];S.append(Paragraph('Recorded fuel checkpoints',sty['Section2']))
    if rows:
        a,b=rows[0],rows[-1]
        stats=[('Checkpoints',str(len(rows))),('Unobserved route fixes',str(len(state.get('skipped_waypoints',[])))),('First measured FOB',fkg(a.get('actual_kg'))),('Last measured FOB',fkg(b.get('actual_kg'))),('Last reference FOB',fkg(b.get('planned_kg'))),('Last difference',fkg(b.get('delta_kg')))]
        S.append(table_for(stats));S.append(Spacer(1,8))
        ch=graph_pil(rows)
        if ch:S.append(RLImage(io.BytesIO(ch),width=502,height=153))
        S.append(Paragraph('Reference FOB comes from SimBrief navlog or imported CSV. GPS proximity does not verify the active FMS leg.',sty['Tiny2']))
        S.append(PageBreak())
        S.append(Paragraph('Waypoint measurements',sty['Section2']))
        heads=['UTC time','Waypoint','Actual FOB','Reference FOB','Delta','GPS proximity']
        data=[[Paragraph(s,sty['Tiny2']) for s in heads]]
        for r in rows:
            tm=dt.datetime.fromtimestamp(r['timestamp'],dt.timezone.utc).strftime('%H:%M:%S')
            dist=f"{r['distance_nm']:.2f} NM" if r.get('distance_nm') is not None else '—'
            vals=[tm, r['ident'], fkg(r['actual_kg']),fkg(r['planned_kg']),fkg(r['delta_kg']),dist]
            data.append([Paragraph(str(s),sty['Tiny2']) for s in vals])
        t=Table(data,colWidths=[65,75,87,93,76,108],repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dfeaf4')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f7fafc')]),('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#e0e5eb')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),2),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
        S.append(t)
    else:S.append(Paragraph('No checkpoints imported.',sty['Small2']))
    if TELEM_STORE.count:
        S.append(Paragraph('Continuous flight telemetry (5-second samples)',sty['Section2']))
        S.append(table_for([('Telemetry samples',str(TELEM_STORE.count)),('Collection interval','5 seconds, subject to SimConnect availability'),('Data export','Full-resolution telemetry included separately in evidence ZIP')]))
        S.append(Paragraph('The recorded FOB change is not interchangeable with engine fuel flow. Refueling, APU operation, simulator changes and sampling gaps may affect comparison.',sty['Tiny2']))
        chart=telemetry_trend_png(TELEM_STORE.profile(2100))
        if chart:
            S.append(Spacer(1,10))
            S.append(RLImage(io.BytesIO(chart),width=504,height=382))
    snaps=state['snapshots']
    if snaps:
        S.append(Paragraph('FMS and flight-phase observations',sty['Section2']))
        for s in snaps:
            entries=[('Issue category',ISSUE_TYPES.get(s.get('issue_type'), 'General observation')),('Phase',s.get('phase')),('Time UTC',s.get('timestamp')),('Waypoint',s.get('waypoint')),('FMS Dest EFOB (kg)',s.get('fms_efob_kg')),
                     ('Actual FOB (kg)',s.get('actual_fob_kg')),('Engine 1 FF (kg/h)',s.get('ff1_kg_h')),('Engine 2 FF (kg/h)',s.get('ff2_kg_h')),
                     ('Altitude (ft)',s.get('altitude_ft')),('Notes',s.get('note')),('GPS latitude',s.get('lat')),('GPS longitude',s.get('lon')),('GPS origin',s.get('context_source')),('GS (kt)',s.get('groundspeed_kt')),('Nearest OFP waypoint',s.get('nearest_ofp_waypoint')),('Distance NM',s.get('distance_to_ofp_waypoint_nm'))]
            filtered=[(k,v) for k,v in entries if v not in ('',None)]
            S.append(KeepTogether([table_for(filtered if filtered else [('Phase','—')]), Spacer(1,8)]))

    def add_evidence_image(ev, local_number=None, group=None):
        path=file_for(ev)
        if not path:return
        S.append(PageBreak())
        prefix=('Screenshot '+str(local_number)) if local_number is not None else 'Independent screenshot'
        S.append(Paragraph(prefix+' – '+xml_escape(printable(ev.get('phase',''))),sty['Section2']))
        if group:
            S.append(Paragraph('Event group: '+xml_escape(safe_str(group.get('title'),140)),sty['Small2']))
            if group.get('remark'):
                S.append(Paragraph('Shared remark: '+xml_escape(safe_str(group['remark'],550)),sty['Small2']))
        if ev.get('purpose'):
            S.append(Paragraph('Evidence type: '+xml_escape(printable(ev.get('purpose'))),sty['Small2']))
        if ev.get('observation_id'):
            related=next((x for x in state.get('snapshots',[]) if x.get('id')==ev['observation_id']),None)
            if related:
                S.append(Paragraph('Linked observation: '+xml_escape(printable(related.get('issue_type'))+' / '+printable(related.get('phase'))+' / '+printable(related.get('timestamp'))),sty['Small2']))
        S.append(Paragraph('Time: '+xml_escape(printable(ev.get('timestamp'))),sty['Small2']))
        cx=ev.get('context') or {}
        props=[('GPS lat / lon',str(cx.get('lat'))+' / '+str(cx.get('lon')) if cx.get('lat') is not None and cx.get('lon') is not None else 'Unavailable'),
               ('GPS source',cx.get('context_source')),('Telemetry age (seconds)',cx.get('telemetry_age_seconds')),
               ('Nearest OFP waypoint',cx.get('nearest_ofp_waypoint')),('Distance to waypoint (NM)',cx.get('distance_to_ofp_waypoint_nm')),
               ('Altitude (ft)',cx.get('altitude_ft')),('Groundspeed (kt)',cx.get('groundspeed_kt')),
               ('IAS (kt)',cx.get('ias_kt')),('Vertical speed (ft/min)',cx.get('vertical_speed_fpm')),
               ('FOB (kg)',cx.get('fob_kg')),('FF1 / FF2 (kg/h)',str(cx.get('ff1_kg_h'))+' / '+str(cx.get('ff2_kg_h'))),
               ('Wind',str(cx.get('wind_from_deg'))+' deg / '+str(cx.get('wind_speed_kt'))+' kt')]
        S.append(table_for(props));S.append(Spacer(1,6))
        S.append(Paragraph('Screenshot remark: '+xml_escape(printable(ev.get('note'))) if ev.get('note') else 'Screenshot remark: Not entered',sty['Small2']))
        with Image.open(path) as img: iw,ih=img.size
        scale=min(500/iw,400/ih)
        S.append(Spacer(1,8));S.append(RLImage(str(path),width=iw*scale,height=ih*scale))

    audits={entry['id']:entry for entry in evidence_audit(state)}
    if state.get('groups'):
        S.append(PageBreak())
        S.append(Paragraph('Linked evidence sequences',sty['Section2']))
        S.append(Paragraph('Screenshots are presented in the user-defined sequence. Each image retains its own SimConnect time and position; manual uploads are marked as such.',sty['Small2']))
    for group in state.get('groups',[]):
        S.append(Spacer(1,14))
        S.append(Paragraph('Event '+xml_escape(group['id'][:8])+': '+xml_escape(printable(group.get('title'))),sty['Section2']))
        S.append(Paragraph('Issue: '+xml_escape(ISSUE_TYPES.get(group.get('issue_type'),'Other / general observation')),sty['Small2']))
        S.append(Paragraph('Shared remark: '+xml_escape(safe_str(group.get('remark'),4000)) if group.get('remark') else 'Shared remark: Not entered',sty['Small2']))
        obs=[v for v in state['snapshots'] if v.get('group_id')==group['id']]
        saves=[v for v in state.get('autosaves',[]) if v.get('group_id')==group['id']]
        imgs=ordered_screenshots(state,group)
        S.append(Paragraph(f'{len(imgs)} linked screenshots | {len(obs)} manual observations | {len(saves)} OIS autosaves (separate ZIP attachments)',sty['Tiny2']))
        audit=audits.get(group['id'],{})
        missing=[x['id'].replace('_',' ') for x in audit.get('requirements',[]) if not x['done']]
        if missing:
            S.append(Paragraph('Evidence not provided: '+xml_escape(', '.join(missing))+' (report export unaffected)',sty['Tiny2']))
        for observation in obs:
            S.append(Paragraph('FMS / manual observation: '+xml_escape(printable(observation.get('timestamp')))+' · EFOB '+xml_escape(printable(observation.get('fms_efob_kg')))+' kg · FOB '+xml_escape(printable(observation.get('actual_fob_kg')))+' kg · '+xml_escape(printable(observation.get('note'))),sty['Tiny2']))
        for index,ev in enumerate(imgs,1):
            add_evidence_image(ev,index,group)
    for ev in state['evidence']:
        if not ev.get('group_id') or not get_group(state,ev.get('group_id')):
            add_evidence_image(ev)
    out=io.BytesIO();doc=NumberedDoc(out);doc.build(S);return out.getvalue()

def make_report(state):
    return make_report_v07(state,TELEM_STORE,file_for,graph_pil,telemetry_trend_png,evidence_audit,checklist,ISSUE_TYPES)

def event_overview(state):
    ev=event_list(state)
    return {'events':event_summary(ev),'geometry':geometry(state.get('route_fixes',[]),TELEM_STORE.profile(1800),ev)}

def clean_csv(rows):
    f=io.StringIO();w=csv.writer(f);w.writerow(['timestamp','timestamp_utc','ident','actual_fob_kg','planned_fob_kg','delta_kg','gps_distance_nm'])
    for r in rows:w.writerow([r.get('timestamp'),fmt_utc(r.get('timestamp')),r['ident'],r.get('actual_kg'),r.get('planned_kg'),r.get('delta_kg'),r.get('distance_nm')])
    return f.getvalue().encode('utf-8-sig')

def telemetry_csv(state):
    """Return full append-only telemetry; retain v0.2 in-memory compatibility."""
    raw=TELEM_STORE.data()
    if raw:return raw
    f=io.StringIO();w=csv.writer(f)
    oldfields=['timestamp_utc','fob_kg','ff1_kg_h','ff2_kg_h','lat','lon','altitude_ft','groundspeed_kt','on_ground','vertical_speed_fpm']
    w.writerow(oldfields)
    for row in state.get('telemetry',[]):
        w.writerow([fmt_utc(row.get('timestamp'))]+[row.get(k) for k in oldfields[1:]])
    return f.getvalue().encode('utf-8-sig')

def make_bundle(state):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('A350_Fuel_Evidence_Report.pdf',make_report(state))
        z.writestr('waypoint_fuel_checkpoints.csv',clean_csv(state['samples']))
        if TELEM_STORE.count or state.get('telemetry'):
            z.writestr('continuous_5s_telemetry.csv',telemetry_csv(state))
        if state.get('ofp') and file_for(state['ofp']):
            pdf,_=redact_pdf(file_for(state['ofp']).read_bytes(),state['meta'].get('redact_terms',''))
            z.writestr('OFP_redacted.pdf' if state['meta'].get('redact_terms','').strip() else 'OFP_NOT_REDACTED.pdf',pdf)
        for i,asset in enumerate(state.get('autosaves',[]),1):
            if file_for(asset):z.write(file_for(asset),f'ois_autosaves/OIS_autosave_{i:03d}.bin')
        for i,ev in enumerate(state['evidence']):
            p=file_for(ev)
            if p:z.write(p,f'screenshots/screenshot_{i+1:02d}.png')
        z.writestr('screenshot_contexts.json',json.dumps([{'index':i+1,'name':ev.get('original'),'timestamp':ev.get('timestamp'),'note':ev.get('note'),'purpose':ev.get('purpose'),'phase':ev.get('phase'),'capture_source':ev.get('capture_source','uploaded'),'capture_mode':ev.get('capture_mode'),'group_id':ev.get('group_id',''),'context':ev.get('context')} for i,ev in enumerate(state.get('evidence',[]))],indent=2,ensure_ascii=False))
        z.writestr('event_timeline.json',json.dumps(event_summary(event_list(state)),indent=2,ensure_ascii=False))
        z.writestr('engine_ff_source_configuration.json',json.dumps({'configured_sources':load_profile(ENGINE_PROFILE_PATH),'warning':'iniBuilds L:INI_FUEL_FLOW1/2 in kg/s is user-confirmed against ECAM; revalidate after aircraft updates. Other custom profiles remain user responsibility.'},indent=2))
        z.writestr('route_evidence_geometry.json',json.dumps(event_overview(state)['geometry'],indent=2,ensure_ascii=False))
        z.writestr('event_groups.json',json.dumps({'groups':state.get('groups',[]),'observations':state.get('snapshots',[]),'autosaves':[{'id':a.get('id'),'original':a.get('original'),'group_id':a.get('group_id')} for a in state.get('autosaves',[])],'audit':evidence_audit(state)},indent=2,ensure_ascii=False))
        z.writestr('README.txt','Fuel evidence package. All screenshots and OFP pages must be visually checked for identifying information before distribution. OIS .bin files are separate ZIP files, not embedded PDF pages. Missing material never prevents export.\n')
    return out.getvalue()

BRIDGE = Bridge(load,save,LOCK,TELEM_STORE,engine_profile_path=ENGINE_PROFILE_PATH)

def add_route_context(context,state):
    """Nearest geographical SimBrief point only, never claim active FMS leg."""
    if context.get('lat') is None or context.get('lon') is None:return context
    from simbridge import haversine_nm
    valid=[]
    for wp in state.get('route_fixes',[]):
        try:valid.append((haversine_nm(context['lat'],context['lon'],wp['lat'],wp['lon']),wp))
        except (ValueError,KeyError,TypeError):continue
    if valid:
        distance,wp=min(valid,key=lambda v:v[0]);context['nearest_ofp_waypoint']=wp.get('ident')
        context['distance_to_ofp_waypoint_nm']=round(distance,3)
        context['nearest_waypoint_note']='Nearest geographically, not verified active FMS waypoint'
    return context

def capture_evidence(mode='msfs_monitor',purpose='other',phase='Auto',note='',observation_id='',group_id=''):
    """Record the event time *before* calling the screen grabber."""
    now=time.time()
    state_at_trigger=load()
    if not group_id:group_id=state_at_trigger.get('active_capture_group_id','')
    ensure_group(state_at_trigger,group_id)
    context=freeze_sim_context(dict(BRIDGE.status),now)
    context=add_route_context(context,state_at_trigger)
    captured=grab_screen(mode)
    raw,dimensions=captured[:2]
    context['screen_capture']=captured[2] if len(captured)>2 else {'capture_mode':mode,'method':'legacy'}
    with LOCK:
        state=load()
        ensure_group(state,group_id)
        if observation_id and not any(v.get('id')==observation_id for v in state['snapshots']):
            raise ValueError('Linked observation not found')
        phase_inferred=phase in ('','Auto')
        if phase_inferred:
            vs=context.get('vertical_speed_fpm')
            if purpose=='preflight_prediction' and context.get('flight_status')=='GROUND':
                final_phase='Preflight'
            elif context.get('flight_status') in ('GROUND','LANDED'):
                final_phase='Ground'
            elif context.get('flight_status')=='AIRBORNE':
                final_phase=('Climb' if isinstance(vs,(float,int)) and vs>300 else
                             'Descent' if isinstance(vs,(float,int)) and vs< -300 else 'Cruise')
            else:final_phase='Other'
        else:final_phase=phase
        item=upload('MSFS_Capture_'+str(int(now))+'.png',base64.b64encode(raw).decode('ascii'),
                    'screenshot',final_phase,context['event_time_utc'],note,purpose,observation_id,group_id)
        item.update({'context':context,'capture_mode':mode,'capture_source':'app_capture','phase_inferred':phase_inferred,
                     'original_dimensions':list(dimensions),'remark_pending':not bool(note.strip())})
        state['evidence'].append(item)
        if group_id: assign_screenshot(state,item['id'],group_id)
        save(state)
        return item,state

HOTKEY = GlobalCaptureHotkey(lambda: capture_evidence('msfs_monitor','other','Auto'))


class ReporterHTTPServer(ThreadingHTTPServer):
    # Windows SO_REUSEADDR can let a second instance steal an existing listener.
    allow_reuse_address = False

    def server_bind(self):
        if os.name == 'nt':
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class Handler(BaseHTTPRequestHandler):
    server_version='A350FuelReporter/' + APP_VERSION
    def log_message(self, fmt,*args): print('[A350]',fmt%args)
    def local_request(self):
        port = self.server.server_address[1]
        allowed_hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
        if port == 80: allowed_hosts.update(('127.0.0.1', 'localhost'))
        if self.headers.get('Host', '').lower() not in allowed_hosts:
            self.respond(403, {'error':'Local Host header required'}); return False
        origin = self.headers.get('Origin')
        if origin and origin not in {f'http://{host}' for host in allowed_hosts}:
            self.respond(403, {'error':'Cross-origin request rejected'}); return False
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':
            self.respond(403, {'error':'Cross-site request rejected'}); return False
        return True
    def respond(self,status,payload,ctype='application/json',filename=None):
        if isinstance(payload,(dict,list)):payload=json.dumps(payload,ensure_ascii=False).encode('utf-8')
        elif isinstance(payload,str):payload=payload.encode('utf-8')
        self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(payload)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self' 'unsafe-inline' data: blob:; connect-src 'self'; img-src 'self' data: blob:")
        if filename:self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
        self.end_headers();self.wfile.write(payload)
    def do_GET(self):
        if not self.local_request(): return
        u=urlparse(self.path);path=u.path
        legal = {'/legal/license': ('LICENSE', 'text/plain; charset=utf-8'),
                 '/legal/notices': ('THIRD_PARTY_NOTICES.md', 'text/plain; charset=utf-8'),
                 '/legal/source-info': ('SOURCE_ACCESS.md', 'text/plain; charset=utf-8')}
        if path in legal:
            name, ctype = legal[path]
            self.respond(200, (BASE/name).read_bytes(), ctype); return
        if path == '/legal/corresponding-source.zip':
            root = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else BASE
            source = root / 'CORRESPONDING_SOURCE.zip'
            if not source.is_file():
                self.respond(404, {'error':'Download the separate full source asset of this release; see Source package guide.'}); return
            self.send_response(200)
            self.send_header('Content-Type','application/zip')
            self.send_header('Content-Length',str(source.stat().st_size))
            self.send_header('Content-Disposition','attachment; filename="CORRESPONDING_SOURCE.zip"')
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            with source.open('rb') as stream:
                while chunk := stream.read(1024*1024): self.wfile.write(chunk)
            return
        if path == '/legal/source.zip':
            root = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else BASE
            source = root / 'APPLICATION_SOURCE.zip'
            if not source.is_file(): self.respond(404, {'error':'Source archive is supplied with the packaged build'}); return
            self.respond(200, source.read_bytes(), 'application/zip', 'APPLICATION_SOURCE.zip'); return
        if path=='/static/v07.js':
            self.respond(200,(BASE/'static'/'v07.js').read_bytes(),'application/javascript; charset=utf-8');return
        if path=='/static/flight_profile.js':
            self.respond(200,(BASE/'static'/'flight_profile.js').read_bytes(),'application/javascript; charset=utf-8');return
        if path in ('/','/index.html'):
            page=(BASE/'static'/'index.html').read_text(encoding='utf-8')
            self.respond(200,page.replace('{{APP_VERSION}}',APP_VERSION),'text/html; charset=utf-8');return
        if path=='/api/version':self.respond(200,{'version':APP_VERSION,'name':'A350 Fuel Evidence Reporter'});return
        if path=='/api/state':self.respond(200,load());return
        if path=='/api/checklist':self.respond(200,checklist(load(),TELEM_STORE.count));return
        if path=='/api/event-overview':self.respond(200,event_overview(load()));return
        if path=='/api/group-audit':self.respond(200,evidence_audit(load()));return
        if path=='/api/simconnect':self.respond(200,BRIDGE.status);return
        if path=='/api/engine-sources':self.respond(200,load_profile(ENGINE_PROFILE_PATH));return
        if path=='/api/screenshot-target':self.respond(200,target_status());return
        if path=='/api/hotkey-status':self.respond(200,{'registered':HOTKEY.registered,'error':HOTKEY.error,'combo':'Ctrl+Shift+F10'});return
        if path=='/api/telemetry-recent':self.respond(200,{'count':TELEM_STORE.count,'records':TELEM_STORE.recent(120)});return
        if path=='/api/telemetry-profile':self.respond(200,{'count':TELEM_STORE.count,'records':TELEM_STORE.profile(2200)});return
        if path=='/api/config':self.respond(200,{'endpoint':f'http://127.0.0.1:{PORT}/api/waypoint','token':json.loads(CONFIG_PATH.read_text())['token']});return
        if path=='/api/export.pdf':self.respond(200,make_report(load()),'application/pdf','A350_Fuel_Evidence_Report.pdf');return
        if path=='/api/export.zip':self.respond(200,make_bundle(load()),'application/zip','A350_Fuel_Evidence_Package.zip');return
        if path=='/api/export-telemetry.csv':self.respond(200,telemetry_csv(load()),'text/csv; charset=utf-8','A350_Continuous_5s_Telemetry.csv');return
        if path=='/api/export-waypoints.csv':self.respond(200,clean_csv(load()['samples']),'text/csv; charset=utf-8','A350_Waypoint_Checkpoints.csv');return
        if path.startswith('/api/image/'):
            wanted=path.removeprefix('/api/image/')
            s=load()
            if not any(e['id']==wanted for e in s['evidence']):self.respond(404,{'error':'Not found'});return
            p=FILES/wanted
            if p.is_file():self.respond(200,p.read_bytes(),'image/png');return
        self.respond(404,{'error':'Not found'})
    def do_POST(self):
        if not self.local_request(): return
        path=urlparse(self.path).path
        if self.headers.get_content_type() != 'application/json':
            self.respond(415, {'error':'application/json required'}); return
        try:
            length=int(self.headers.get('Content-Length',0))
            if length>140_000_000:self.respond(413,{'error':'Payload too large'});return
            if length<2:raise ValueError('Empty request')
            body=json.loads(self.rfile.read(length).decode('utf-8'))
            state=load()
            if path=='/api/engine-sources':
                saved=save_profile(ENGINE_PROFILE_PATH,body)
                self.respond(200,{'ok':True,'sources':saved,'note':'Direct LVar requests reload on the next SimConnect poll. Positive values must still be checked against the cockpit.'});return
            if path=='/api/scan-aircraft-lvars':
                result=scan_lvars(str(body.get('folder') or ''))
                self.respond(200,result);return
            if path=='/api/simbrief-import':
                uid=str(body.get('user_id','')).strip()
                record=fetch_latest(uid)
                # Do not mix samples from one flight with a newly imported OFP.
                if state['samples'] and (state['meta'].get('dep') not in ('',record['meta']['dep']) or state['meta'].get('arr') not in ('',record['meta']['arr'])):
                    raise ValueError('Existing measurements belong to another route. Start a new case first.')
                for k,v in record['meta'].items():
                    if v is not None and str(v)!='':state['meta'][k]=str(v)
                state['route_fixes']=record['route_fixes']
                state['skipped_waypoints']=[]
                state['simbrief_user_id']=uid
                pdf_status='No PDF link from SimBrief'
                if record.get('pdf_url'):
                    try:
                        raw=download_pdf(record['pdf_url'])
                        item=upload('SimBrief_OFP.pdf',base64.b64encode(raw).decode('ascii'),'ofp')
                        state['ofp']=item;pdf_status='PDF imported'
                    except Exception as err:pdf_status='PDF could not be fetched: '+str(err)
                save(state);self.respond(200,{'ok':True,'state':state,'navlog_count':record['navlog_count'],'pdf_status':pdf_status});return
            if path=='/api/connect':
                state['tracking_enabled']=True
                save(state)
                BRIDGE.start()
                self.respond(200,{'ok':True,'state':state,'connection':BRIDGE.status});return
            if path=='/api/disconnect':
                state['tracking_enabled']=False
                save(state)
                BRIDGE.stop()
                self.respond(200,{'ok':True,'state':state});return
            if path=='/api/tracking':
                desired=bool(body.get('enabled'))
                # Continuous telemetry can run without SimBrief; waypoint matches require an imported route.
                state['tracking_enabled']=desired
                save(state);self.respond(200,{'ok':True,'state':state});return
            if path=='/api/capture-screenshot':
                mode=str(body.get('mode','msfs_monitor'))
                purpose=safe_str(body.get('purpose','other'),60)
                phase=safe_str(body.get('phase','Auto'),60)
                note=safe_str(body.get('note',''),600)
                observation_id=safe_str(body.get('observation_id',''),40)
                group_id=ensure_group(state,safe_str(body.get('group_id',''),40))
                item,new_state=capture_evidence(mode,purpose,phase,note,observation_id,group_id)
                self.respond(200,{'ok':True,'item':item,'state':new_state});return
            if path=='/api/active-capture-group':
                state['active_capture_group_id']=ensure_group(state,str(body.get('group_id','')))
                save(state);self.respond(200,{'ok':True,'state':state});return
            if path=='/api/group-create':
                group=new_group(body.get('title',''),body.get('issue_type','other'),body.get('remark',''))
                state.setdefault('groups',[]).append(group)
                save(state);self.respond(200,{'ok':True,'group':group,'state':state});return
            if path=='/api/group-anchor':
                group=get_group(state,str(body.get('id','')))
                if not group:raise ValueError('Unknown group')
                capture_id=str(body.get('capture_id',''))
                candidates=[x.get('id') for x in state['evidence']+state['snapshots'] if x.get('group_id')==group['id']]
                if capture_id and capture_id not in candidates:raise ValueError('Anchor must be linked to event')
                group['anchor_capture_id']=capture_id
                save(state);self.respond(200,{'ok':True,'state':state});return
            if path=='/api/group-update':
                group=get_group(state,str(body.get('id','')))
                if not group:raise ValueError('Unknown group')
                if 'title' in body:group['title']=safe_str(body['title'],120)
                if 'remark' in body:group['remark']=safe_str(body['remark'],4000)
                if 'issue_type' in body:
                    if body['issue_type'] not in (*ISSUE_TYPES,'other'):raise ValueError('Unknown issue type')
                    group['issue_type']=body['issue_type']
                save(state);self.respond(200,{'ok':True,'state':state});return
            if path=='/api/group-assign-screenshot':
                assign_screenshot(state,str(body.get('screenshot_id','')),str(body.get('group_id','')))
                save(state);self.respond(200,{'ok':True,'state':state});return
            if path=='/api/group-move-screenshot':
                reorder_screenshot(state,str(body.get('group_id','')),str(body.get('screenshot_id','')),int(body.get('direction',0)))
                save(state);self.respond(200,{'ok':True,'state':state});return
            if path=='/api/group-assign-autosave':
                b=next((x for x in state.get('autosaves',[]) if x.get('id')==body.get('autosave_id')),None)
                if not b:raise ValueError('Autosave not found')
                b['group_id']=ensure_group(state,str(body.get('group_id','')))
                save(state);self.respond(200,{'ok':True,'state':state});return
            if path in ('/api/remark','/api/evidence-update'):
                ident=str(body.get('id',''))
                ev=next((item for item in state['evidence'] if item.get('id')==ident),None)
                if not ev:raise ValueError('Screenshot not found')
                if 'note' in body:ev['note']=safe_str(body.get('note',''),1000)
                if 'purpose' in body:
                    if body['purpose'] not in ('preflight_prediction','fms_fuel_load','engine_ff','landing_fob','other'):
                        raise ValueError('Unknown screenshot evidence type')
                    ev['purpose']=body['purpose']
                if 'phase' in body:
                    if body['phase'] not in ('Pushback','Preflight','Climb','Cruise','Descent','Runway vacated','Other','Ground'):
                        raise ValueError('Unknown flight phase')
                    ev['phase']=body['phase']
                if 'observation_id' in body:
                    new_link=safe_str(body.get('observation_id',''),40)
                    if new_link and not any(x.get('id')==new_link for x in state['snapshots']):
                        raise ValueError('Referenced observation not found')
                    ev['observation_id']=new_link
                if 'group_id' in body:assign_screenshot(state,ident,str(body.get('group_id','')))
                ev['remark_pending']=not bool(ev.get('note','').strip())
                save(state)
                self.respond(200,{'ok':True,'state':state});return
            if path=='/api/marker':
                cx=add_route_context(freeze_sim_context(dict(BRIDGE.status)),state)
                marker={'id':secrets.token_hex(8),'context':cx}
                state.setdefault('markers',[]).append(marker)
                save(state)
                self.respond(200,{'ok':True,'marker':marker,'state':state});return
            if path=='/api/new-case':
                if state.get('tracking_enabled'):raise ValueError('Stop automatic tracking first')
                new_state=deepcopy(DEF);new_state['flight_id']=secrets.token_hex(12)
                save(new_state)
                TELEM_STORE.clear()
                BRIDGE.reset_session()
                for old in FILES.iterdir():
                    if old.is_file():old.unlink()
                self.respond(200,{'ok':True,'state':load()});return
            if path=='/api/waypoint':
                token=json.loads(CONFIG_PATH.read_text())['token']
                if self.headers.get('X-Reporter-Token')!=token:self.respond(403,{'error':'Invalid integration token'});return
                merge_samples(state,[sample_from(body)]);save(state)
                self.respond(200,{'ok':True,'count':len(state['samples'])});return
            if path=='/api/issues':
                issue_types=body.get('case_types',[])
                if not isinstance(issue_types,list) or any(t not in ISSUE_TYPES for t in issue_types):raise ValueError('Invalid issue selection')
                state['case_types']=[t for t in ISSUE_TYPES if t in issue_types]
            elif path=='/api/meta':
                for k in DEF['meta']:
                    if k in body:state['meta'][k]=safe_str(body[k],1000 if k in ('notes','redact_terms') else 120)
            elif path=='/api/import-csv':
                raw=base64.b64decode(body['data'],validate=True)
                if len(raw)>8*1024*1024:raise ValueError('CSV too large')
                merge_samples(state,ingest_csv(raw.decode('utf-8-sig')))
            elif path=='/api/snapshot':
                shot={k:safe_str(body.get(k),1000 if k=='note' else 400) for k in ('issue_type','phase','timestamp','waypoint','fms_efob_kg','actual_fob_kg','ff1_kg_h','ff2_kg_h','altitude_ft','note')}
                reference_id=str(body.get('reference_capture_id',''))
                linked=next((v for v in state['evidence'] if v['id']==reference_id),None)
                marker=next((v for v in state.get('markers',[]) if v['id']==reference_id),None)
                # Use screenshot/marker event position when entered later; never pretend
                # that submission-time coordinates describe an earlier screenshot.
                cx=((linked or marker).get('context') if (linked or marker) else add_route_context(freeze_sim_context(dict(BRIDGE.status)),state))
                group_id=ensure_group(state,safe_str(body.get('group_id',''),40))
                if not group_id and shot['issue_type'] in ISSUE_TYPES:
                    # Each new incident gets an explicit case even when the user skips setup.
                    group=new_group(shot['issue_type'].replace('_',' ').title()+' · '+(shot.get('timestamp') or 'observation'),shot['issue_type'],shot['note'])
                    state.setdefault('groups',[]).append(group);group_id=group['id']
                shot.update({'group_id':group_id,'context':cx,'context_source':cx.get('context_source'),
                             'lat':cx.get('lat'),'lon':cx.get('lon'),
                             'nearest_ofp_waypoint':cx.get('nearest_ofp_waypoint'),
                             'distance_to_ofp_waypoint_nm':cx.get('distance_to_ofp_waypoint_nm'),
                             'groundspeed_kt':cx.get('groundspeed_kt'),
                             'reference_capture_id':reference_id})
                if cx.get('context_status')=='fresh_simconnect':
                    for key in ('actual_fob_kg','ff1_kg_h','ff2_kg_h','altitude_ft'):
                        data_key={'actual_fob_kg':'fob_kg','ff1_kg_h':'ff1_kg_h','ff2_kg_h':'ff2_kg_h','altitude_ft':'altitude_ft'}[key]
                        if not shot[key] and cx.get(data_key) is not None:shot[key]=str(cx[data_key])
                if not shot.get('timestamp') or reference_id:
                    shot['timestamp']=cx.get('event_time_utc','')
                shot['id']=secrets.token_hex(8);state['snapshots'].append(shot)
            elif path=='/api/attachment':
                category=body.get('category')
                group_id=ensure_group(state,safe_str(body.get('group_id',''),40))
                item=upload(body.get('name',''),body.get('data',''),category,body.get('phase',''),body.get('timestamp',''),body.get('note',''),body.get('purpose',''),body.get('observation_id',''),group_id)
                if category=='screenshot' and item.get('observation_id') and not any(s['id']==item['observation_id'] for s in state['snapshots']):
                    (FILES/item['id']).unlink(missing_ok=True);raise ValueError('Observation not found; save it before attaching screenshots')
                if category=='screenshot':
                    # A later upload has no trustworthy time/location by itself.
                    if item.get('observation_id'):
                        linked=next((s for s in state['snapshots'] if s['id']==item['observation_id']),None)
                        if linked and linked.get('context'):
                            item['context']=linked['context'];item['context_source']='linked_observation'
                    item.setdefault('capture_source','manual_upload')
                    item['remark_pending']=not bool(item.get('note'))
                    state['evidence'].append(item)
                    if group_id:assign_screenshot(state,item['id'],group_id)
                elif category=='bin':
                    state.setdefault('autosaves',[]).append(item)
                    state['bin']=None
                else:state[category]=item
            elif path=='/api/delete':
                typ=body.get('type');ident=body.get('id')
                if typ=='screenshot':
                    state['evidence']=[x for x in state['evidence'] if x['id']!=ident]
                    for group in state.get('groups',[]):group['screenshot_ids']=[x for x in group.get('screenshot_ids',[]) if x!=ident]
                    (FILES/str(ident)).unlink(missing_ok=True)
                elif typ=='snapshot':state['snapshots']=[x for x in state['snapshots'] if x['id']!=ident]
                elif typ=='autosave':
                    state['autosaves']=[x for x in state.get('autosaves',[]) if x['id']!=ident]
                    (FILES/str(ident)).unlink(missing_ok=True)
                elif typ=='group':
                    if not get_group(state,ident):raise ValueError('Group not found')
                    state['groups']=[x for x in state['groups'] if x['id']!=ident]
                    if state.get('active_capture_group_id')==ident:state['active_capture_group_id']=''
                    for ev in state['evidence']:
                        if ev.get('group_id')==ident:ev['group_id']=''
                    for ev in state['snapshots']:
                        if ev.get('group_id')==ident:ev['group_id']=''
                    for ev in state['autosaves']:
                        if ev.get('group_id')==ident:ev['group_id']=''
                elif typ in ('ofp','bin'):state[typ]=None
                elif typ=='samples':state['samples']=[]
                else:raise ValueError('Unknown delete type')
            else:self.respond(404,{'error':'Not found'});return
            save(state);self.respond(200,{'ok':True,'state':state})
        except Exception as e:
            self.respond(400,{'error':str(e)})

def main():
    ensure()
    # Bind before arming recording/hotkeys. An older reporter often owns this port,
    # which would otherwise leave users viewing the old EXE in their browser.
    try:
        server=ReporterHTTPServer(('127.0.0.1',PORT),Handler)
    except OSError as exc:
        print(f'\nA350 Fuel Evidence Reporter v{APP_VERSION} could not start: {exc}')
        print(f'Port {PORT} is already in use. Close other A350FuelReporter processes,')
        print(f'then restart. Check the running backend at http://127.0.0.1:{PORT}/api/version')
        return
    # Connection and recording are only started by the user.
    state=load()
    if state.get('tracking_enabled'):
        state['tracking_enabled']=False
        save(state)
    HOTKEY.start()
    print(f'\nA350 Fuel Evidence Reporter v{APP_VERSION}\nOpen: http://127.0.0.1:{PORT}\nLocal files: {DATA}\nPress Ctrl+C to stop.\n')
    from threading import Timer
    if os.environ.get('A350_REPORTER_NO_BROWSER') != '1':
        Timer(1.2,lambda: webbrowser.open(f'http://127.0.0.1:{PORT}')).start()
    try:
        server.serve_forever()
    finally:
        BRIDGE.stop()
        server.server_close()

if __name__=='__main__':main()
