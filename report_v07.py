# SPDX-License-Identifier: AGPL-3.0-only
"""Chronological, offline evidence report for iniBuilds flight-data and SimBrief comparisons."""
from __future__ import annotations
import io,html,math,datetime as dt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.platypus import BaseDocTemplate,Frame,PageTemplate,Paragraph,Spacer,Table,LongTable,TableStyle,Image as RLImage,PageBreak,KeepTogether
from PIL import Image
from event_timeline import event_list
from route_map import render_map

PAGE_W,PAGE_H=A4
CW=PAGE_W-84

def escape(x,limit=2000):return html.escape(str(x if x not in (None,'') else 'Not recorded')[:limit]).replace('\n','<br/>')
def val(x):return str(x) if x not in (None,'') else 'Not recorded'
def antiice_label(x):
    try:
        if x is None or str(x).strip()=='':return 'N/A'
        if float(x)==1:return 'ON'
        if float(x)==0:return 'OFF'
    except (TypeError,ValueError):pass
    return 'N/A'

def styles():
    s=getSampleStyleSheet()
    s.add(ParagraphStyle(name='MTitle',parent=s['Title'],fontName='Helvetica-Bold',fontSize=18,leading=22,spaceAfter=12,textColor=colors.HexColor('#102f48')))
    s.add(ParagraphStyle(name='MH',parent=s['Heading2'],fontSize=12,leading=15,spaceBefore=15,spaceAfter=8,textColor=colors.HexColor('#145c83')))
    s.add(ParagraphStyle(name='MText',parent=s['Normal'],fontSize=8.5,leading=12,spaceAfter=5,textColor=colors.HexColor('#294155')))
    s.add(ParagraphStyle(name='MSmall',parent=s['Normal'],fontSize=7.3,leading=10,spaceAfter=4,textColor=colors.HexColor('#35526a')))
    s.add(ParagraphStyle(name='MHeadRow',parent=s['Normal'],fontName='Helvetica-Bold',fontSize=7.2,leading=10,textColor=colors.HexColor('#183e56')))
    return s

class ReportDoc(BaseDocTemplate):
    def __init__(self,stream):
        super().__init__(stream,pagesize=A4,leftMargin=42,rightMargin=42,topMargin=44,bottomMargin=43)
        frame=Frame(self.leftMargin,self.bottomMargin,self.width,self.height,leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
        self.addPageTemplates(PageTemplate(id='normal',frames=[frame],onPage=self.onpage))
    def onpage(self,cv,doc):
        cv.setStrokeColor(colors.HexColor('#d6e1e9'));cv.line(42,29,PAGE_W-42,29)
        cv.setFont('Helvetica',8);cv.setFillColor(colors.HexColor('#567086'))
        cv.drawString(42,18,'A350 FUEL EVIDENCE | RECORDED SIMULATOR DATA')
        cv.drawRightString(PAGE_W-42,18,f'Page {doc.page}')
    def afterFlowable(self,flowable):
        anchor=getattr(flowable,'event_anchor',None)
        if anchor:
            self.canv.bookmarkPage(anchor)
            self.canv.addOutlineEntry(getattr(flowable,'event_title',anchor),anchor,level=0,closed=False)

def kvtable(items,s):
    rows=[[Paragraph(escape(a,100),s['MHeadRow']),Paragraph(escape(b,1500),s['MText'])] for a,b in items]
    t=Table(rows,colWidths=[150,CW-150],hAlign='LEFT')
    t.setStyle(TableStyle([('ROWBACKGROUNDS',(0,0),(-1,-1),[colors.white,colors.HexColor('#f5f9fc')]),
        ('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#dbe5ec')),('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
        ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    return t

def gridtable(headers,rows,widths,s):
    data=[[Paragraph(escape(v,300),s['MHeadRow']) for v in headers]]
    for row in rows:data.append([Paragraph(escape(v,1000),s['MSmall']) for v in row])
    table=LongTable(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e2eef6')),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f7fafc')]),
        ('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#dae4ea')),
        ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),
        ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
    return table

def img(data,max_w,max_h):
    with Image.open(io.BytesIO(data)) as im:
        w,h=im.size
    scale=min(max_w/w,max_h/h)
    return RLImage(io.BytesIO(data),width=w*scale,height=h*scale)

def make_report(state,store,file_for,graph_pil,telemetry_trend_png,evidence_audit,checklist,issue_types):
    S=[];s=styles();m=state.get('meta',{});events=event_list(state)
    records=store.profile(3000) if store.count else []
    # SUMMARY
    S.append(Paragraph('A350 Fuel Evidence Report',s['MTitle']))
    S.append(Paragraph('Recorded observations and SimBrief flight-plan comparison.',s['MSmall']))
    S.append(Paragraph('1. Flight Summary',s['MH']))
    S.append(kvtable([('Date',m.get('date')),('Flight',m.get('flight')),
      ('Route',(m.get('dep') or '—')+' → '+(m.get('arr') or '—')),
      ('Simulator',m.get('sim')),('Aircraft',m.get('variant')),('Cabin',m.get('cabin')),
      ('Add-on version',m.get('version')),('Version origin',m.get('version_source')),
      ('Live weather',m.get('live_weather')),('Live time',m.get('live_time')),
      ('SimBrief block fuel kg',m.get('ofp_block_kg')),('Takeoff fuel kg',m.get('ofp_takeoff_kg')),
      ('Planned trip fuel kg',m.get('ofp_trip_kg')),('Planned destination EFOB kg',m.get('ofp_dest_efob_kg')),
      ('Fuel bias %',m.get('fuel_bias_pct')),('Cost index',m.get('cost_index'))],s))
    S.append(Paragraph('2. Route & Evidence Overview',s['MH']))
    try:S.append(img(render_map(state.get('route_fixes'),records,events),CW,300))
    except Exception as exc:S.append(Paragraph('Route map unavailable: '+escape(exc),s['MSmall']))
    if not events:S.append(Paragraph('No evidence events recorded.',s['MText']))
    else:
        S.append(Paragraph('Chronological event markers (at original GPS positions, never snapped to the OFP route):',s['MSmall']))
        for e in events:
            pos=e.get('position') or {}
            poslabel=(f"{pos['lat']:.5f}, {pos['lon']:.5f}" if pos else 'GPS unavailable')
            S.append(Paragraph(f'<link href="#EV_{e["label"]}" color="#116b9b">{e["label"]}</link> · {escape(e["utc"])} · {escape(e["title"],110)} · {escape(poslabel)}',s['MSmall']))
    # FUEL PLAN COMPARISON
    S.append(Paragraph('3. Fuel Analysis (Simulator vs. SimBrief/OFP)',s['MH']))
    samples=state.get('samples') or []
    if samples:
        ch=graph_pil(samples)
        if ch:S.append(img(ch,CW,170))
        S.append(Paragraph('FOB comparison uses each imported OFP reference / GPS-associated checkpoint. A nearby OFP fix is not proof of an active FMS leg.',s['MSmall']))
        data=[]
        for r in samples:
            t=r.get('timestamp')
            try:utc=dt.datetime.fromtimestamp(float(t),dt.timezone.utc).strftime('%H:%M:%S')
            except (TypeError,ValueError,OverflowError):utc='—'
            data.append([utc,r.get('ident','—'),r.get('actual_kg'),r.get('planned_kg'),r.get('delta_kg'),r.get('distance_nm')])
        S.append(gridtable(['UTC','Fix','Actual kg','OFP kg','Delta kg','GPS NM'],data,[55,75,96,95,88,CW-409],s))
    else:S.append(Paragraph('No waypoint checkpoints recorded; analysis remains available after a SimBrief import or CSV upload.',s['MText']))
    # FLIGHT PROFILE
    S.append(Paragraph('4. Flight Profile (5-second telemetry)',s['MH']))
    S.append(Paragraph('Engine fuel flow, N1 %, altitude, airspeed, FOB, wind and vertical speed on a shared UTC axis. Full-resolution CSV is delivered separately in the ZIP package.',s['MSmall']))
    chart=telemetry_trend_png(store.profile(2100)) if store.count else None
    if chart:S.append(img(chart,CW,370))
    else:S.append(Paragraph('No continuous telemetry recorded.',s['MText']))
    # ANTI-ICE SWITCH-STATE RECORD (not proof of protection effectiveness)
    S.append(Paragraph('Engine Anti-Ice – Recorded Switch States',s['MH']))
    if records:
        summary=[]
        for engine in (1,2):
            field=f'engine{engine}_antiice'
            values=[antiice_label(row.get(field)) for row in records]
            sources=sorted({str(row.get(f'engine{engine}_antiice_source') or '').strip()
                            for row in records if row.get(f'engine{engine}_antiice_source')})
            summary.append([f'Engine {engine}',f'{values.count("ON")} / {values.count("OFF")} / {values.count("N/A")}',
                            '; '.join(sources)[:170] or 'Not available'])
        S.append(gridtable(['Engine','5s samples ON/OFF/N/A','Data source'],summary,[76,153,CW-229],s))
        S.append(Paragraph('Recorded per-engine switch indications, not evidence of effective bleed-air ice protection. Sample counts are not operating hours; short changes between samples may be missed.',s['MSmall']))
        # Report first observed state and subsequent changes at their sampled UTC times.
        # Never infer an exact physical toggle timestamp between samples.
        transition_rows=[]
        for engine in (1,2):
            previous=None
            for row in records:
                status=antiice_label(row.get(f'engine{engine}_antiice'))
                if status=='N/A':continue
                if status!=previous:
                    transition_rows.append((str(row.get('timestamp_utc') or ''), f'Engine {engine}', status,
                                            'First recorded' if previous is None else 'Change observed'))
                previous=status
        transition_rows.sort(key=lambda x:x[0])
        if transition_rows:
            S.append(Paragraph('Anti-Ice State Observations (UTC)',s['MH']))
            S.append(gridtable(['Sample UTC','Engine','State','Observation'],transition_rows[:60],
                               [166,90,72,CW-328],s))
            if len(transition_rows)>60:
                S.append(Paragraph(f'{len(transition_rows)-60} additional anti-ice observations omitted from PDF; complete 5-second data remains in CSV.',s['MSmall']))
            S.append(Paragraph('Times indicate the first recorded sample after a change, not the exact instant the switch was operated.',s['MSmall']))
    else:
        S.append(Paragraph('No engine anti-ice telemetry recorded.',s['MSmall']))
    # TIMELINE
    S.append(Paragraph('5. Chronological Event Timeline',s['MH']))
    if events:
        rows=[]
        for e in events:
            pos=e.get('position') or {}
            xyz=f"{pos['lat']:.4f}, {pos['lon']:.4f}" if pos else 'Position unavailable'
            desc=(e['remark'] or 'No remark')[:140]
            rows.append([f'<link href="#EV_{e["label"]}">{e["label"]}</link>',e['utc'],e['category'],e['title'],xyz,desc])
        # link markup passed raw on first column; escape all other cells
        tbl=[[Paragraph(h,s['MHeadRow']) for h in ['ID','UTC','Category','Event','GPS','Remark']]]
        for r in rows:
            tbl.append([Paragraph(r[0],s['MSmall'])]+[Paragraph(escape(v),s['MSmall']) for v in r[1:]])
        table=LongTable(tbl,colWidths=[35,91,85,106,90,CW-407],repeatRows=1)
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e2eef6')),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f8fafc')]),
            ('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#e0e8ee')),
            ('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4)]))
        S.append(table)
    else:S.append(Paragraph('No events available.',s['MText']))
    # EVIDENCE DETAILS
    S.append(Paragraph('6. Evidence Details',s['MH']))
    if not events:S.append(Paragraph('No screenshot or manual FMS observations.',s['MText']))
    for e in events:
        label=e['label'];anchor=Paragraph(f'{label} · {escape(e["title"])}',s['MH'])
        anchor.event_anchor='EV_'+label;anchor.event_title=label+' '+str(e['title'])[:80]
        S.append(anchor)
        p=e.get('position')
        S.append(Paragraph(f'UTC: {escape(e["utc"])} | Category: {escape(e["category"])} | GPS: '+
                           (f"{p['lat']:.6f}, {p['lon']:.6f}" if p else 'Position unavailable'),s['MSmall']))
        S.append(Paragraph('Shared remark: '+escape(e['remark'],4000),s['MText']))
        if e.get('autosaves'):
            S.append(Paragraph('Separate OIS files in ZIP: '+escape(', '.join(x.get('original','BIN') for x in e['autosaves'])),s['MSmall']))
        for obs in e['observations']:
            S.append(kvtable([('Manual FMS entry UTC',obs.get('timestamp')),('Flight phase',obs.get('phase')),
              ('FMS destination EFOB kg',obs.get('fms_efob_kg')),('Measured FOB kg',obs.get('actual_fob_kg')),
              ('Fuel flow engine 1 kg/h',obs.get('ff1_kg_h')),('Fuel flow engine 2 kg/h',obs.get('ff2_kg_h')),('N1 engine 1 %',obs.get('engine1_n1_pct')),('N1 engine 2 %',obs.get('engine2_n1_pct')),
              ('Engine 1 Anti-Ice',antiice_label(obs.get('engine1_antiice'))),('Engine 2 Anti-Ice',antiice_label(obs.get('engine2_antiice'))),
              ('Manual note',obs.get('note'))],s))
        screenshots=e['screenshots']
        if len(screenshots)>=2:
            S.append(Paragraph(f'Sequence: {len(screenshots)} screenshots in the user-defined before/after order. Individual GPS/FOB/FF values follow.',s['MSmall']))
            preview=[]
            for n,shot in enumerate(screenshots[:3],1):
                path=file_for(shot)
                if not path:continue
                image_bytes=path.read_bytes()
                tile=img(image_bytes,159,98)
                preview.append([Paragraph(f'Screenshot {n}',s['MSmall']),tile])
            # Portrait A4 cannot guarantee cockpit-digit readability in thumbnails.
            # Keep thumbnails as overview, full-size images follow below.
            if preview:
                gallery=Table([[Table([[item[0]],[item[1]]],colWidths=[159]) for item in preview]],colWidths=[CW/len(preview)]*len(preview),hAlign='LEFT')
                S.append(gallery)
                S.append(Paragraph('Preview only — original-resolution screenshots are preserved in the ZIP.',s['MSmall']))
        for n,shot in enumerate(screenshots,1):
            path=file_for(shot)
            S.append(Paragraph(f'{label}.{n} Screenshot — {escape(shot.get("timestamp"))}',s['MText']))
            cx=shot.get('context') or {}
            gps=(f'{cx["lat"]}, {cx["lon"]}' if cx.get('lat') is not None and cx.get('lon') is not None else 'Not available / later upload')
            S.append(Paragraph('GPS '+escape(gps)+' | Altitude ft '+escape(cx.get('altitude_ft'))+' | FOB kg '+escape(cx.get('fob_kg'))+
                 ' | FF1/FF2 kg/h '+escape(cx.get('ff1_kg_h'))+'/'+escape(cx.get('ff2_kg_h'))+
                 ' | N1(1/2) % '+escape(cx.get('engine1_n1_pct'))+'/'+escape(cx.get('engine2_n1_pct'))+
                 ' | Engine Anti-Ice 1/2 '+antiice_label(cx.get('engine1_antiice'))+'/'+antiice_label(cx.get('engine2_antiice'))+
                 ' | OFP-nearest '+escape(cx.get('nearest_ofp_waypoint'))+' | Source '+escape(shot.get('capture_source'))+' | Remark '+escape(shot.get('note'),800),s['MSmall']))
            S.append(Paragraph('Anti-Ice source ENG1: '+escape(cx.get('engine1_antiice_source'))+' | ENG2: '+escape(cx.get('engine2_antiice_source')),s['MSmall']))
            display=cx.get('screen_capture') or {}
            if display.get('monitor'):
                S.append(Paragraph('Screenshot display: '+escape(display.get('monitor'))+' | Capture method: '+escape(display.get('method')),s['MSmall']))
            if path:
                im=img(path.read_bytes(),CW,275)
                S.append(im)
            else:S.append(Paragraph('Screenshot missing on disk; no image inserted.',s['MSmall']))
    # EVIDENCE SUMMARY
    S.append(Paragraph('7. Evidence checklist / Attachment Status',s['MH']))
    audit=evidence_audit(state)
    if audit:
        rows=[]
        for item in audit:
            found=next((e for e in events if e['raw_id']==item['id']),None)
            missing=', '.join(x['id'].replace('_',' ') for x in item.get('requirements',[]) if not x.get('done'))
            rows.append([found['label'] if found else item['id'][:8],item.get('title',''),missing or 'Complete'])
        S.append(gridtable(['Event','Title','Missing evidence (advisory only)'],rows,[55,169,CW-224],s))
    else:S.append(Paragraph('No grouped evidence. Export remains available.',s['MText']))
    S.append(Paragraph('OIS autosave (.bin) files remain separate ZIP attachments; missing evidence never blocks data capture or export. Verify screenshots and OFP for personal data before distribution.',s['MSmall']))
    stream=io.BytesIO();ReportDoc(stream).build(S)
    return stream.getvalue()
