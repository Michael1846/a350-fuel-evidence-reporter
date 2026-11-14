# SPDX-License-Identifier: AGPL-3.0-only
"""Offline, WGS84-referenced route graphic: no map tile server / API needed.
Equirectangular projection with midlatitude cosine. Discontinuities are shown as
breaks, not fabricated flight legs. Longitudes are locally unwrapped at dateline.
"""
import math
import io
from PIL import Image,ImageDraw,ImageFont

def points_from_fixes(fixes):
    out=[]
    for fix in fixes or []:
        try:
            a,b=float(fix['lat']),float(fix['lon'])
            if math.isfinite(a) and math.isfinite(b) and -90<=a<=90 and -180<=b<=180:
                out.append({'lat':a,'lon':b,'name':str(fix.get('ident',''))[:16]})
        except (ValueError,TypeError,KeyError):continue
    return out

def track_from_rows(rows):
    """Split by missing GPS, >25s sample gaps and implausible GPS jumps.
    Upper speed 1100kt is intentionally conservative to avoid accidental joins.
    """
    from math import radians,sin,cos,asin,sqrt
    segments=[];current=[];last_t=None;prior=None
    for r in rows or []:
        try:
            a=float(r['latitude_deg']);b=float(r['longitude_deg']);t=float(r['timestamp_unix'])
            if not (math.isfinite(a) and math.isfinite(b) and math.isfinite(t) and -90<=a<=90 and -180<=b<=180):raise ValueError()
        except (ValueError,TypeError,KeyError):
            if len(current)>1:segments.append(current)
            current=[];prior=None;last_t=None;continue
        broken=False
        if prior:
            dt=t-last_t
            dlat=radians(a-prior[0]);dlon=radians((b-prior[1]+180)%360-180)
            z=sin(dlat/2)**2+cos(radians(a))*cos(radians(prior[0]))*sin(dlon/2)**2
            dist=3440.065*2*asin(min(1,sqrt(z)))
            if dt<=0 or dt>25 or (dist/dt*3600)>1100:broken=True
        if broken:
            if len(current)>1:segments.append(current)
            current=[]
        current.append({'lat':a,'lon':b,'t':t})
        last_t=t;prior=(a,b)
    if len(current)>1:segments.append(current)
    return segments

def geometry(fixes,tracks,events):
    planned=points_from_fixes(fixes)
    actual=track_from_rows(tracks)
    markers=[{'label':e['label'],'lat':e['position']['lat'],'lon':e['position']['lon'],'title':e['title']}
             for e in events if e.get('position')]
    allp=planned+[p for s in actual for p in s]+markers
    if not allp:return {'planned':planned,'actual':actual,'events':markers,'bounds':None,'unwrap_center':0}
    # Central longitude around largest empty circular arc; minimizes dateline spread.
    raw=sorted((p['lon']+360)%360 for p in allp)
    gaps=[(raw[(i+1)%len(raw)] + (360 if i+1==len(raw) else 0) - raw[i],i) for i in range(len(raw))]
    _,idx=max(gaps)
    start=raw[(idx+1)%len(raw)]
    unwrap=lambda lon: ((lon+360)%360 - start)%360
    left,right=min(unwrap(p['lon']) for p in allp),max(unwrap(p['lon']) for p in allp)
    lo,hi=min(p['lat'] for p in allp),max(p['lat'] for p in allp)
    return {'planned':planned,'actual':actual,'events':markers,'bounds':{'lat_min':lo,'lat_max':hi,'lon_min':left,'lon_max':right},'unwrap_center':start}

def render_map(fixes,tracks,events,width=1500,height=800):
    g=geometry(fixes,tracks,events)
    im=Image.new('RGB',(width,height),'#f7fbfe');d=ImageDraw.Draw(im)
    bounds=g['bounds']
    if not bounds:
        d.text((35,30),'Route unavailable: no georeferenced OFP, track or event positions',fill='#486379')
        b=io.BytesIO();im.save(b,format='PNG');return b.getvalue()
    start=g['unwrap_center']
    unwrap=lambda lon: ((lon+360)%360 - start)%360
    x0,y0=75,50; x1,y1=width-70,height-82
    midlat=(bounds['lat_min']+bounds['lat_max'])/2
    compression=max(.08,math.cos(math.radians(midlat)))
    xr=max((bounds['lon_max']-bounds['lon_min'])*compression,.02)
    yr=max(bounds['lat_max']-bounds['lat_min'],.02)
    scale=min((x1-x0)/xr,(y1-y0)/yr)
    cx=(bounds['lon_min']+bounds['lon_max'])/2;cy=(bounds['lat_min']+bounds['lat_max'])/2
    def xy(p):return (round((x0+x1)/2+(unwrap(p['lon'])-cx)*compression*scale),round((y0+y1)/2-(p['lat']-cy)*scale))
    for k in range(7):
        x=x0+(x1-x0)*k/6;d.line((x,y0,x,y1),fill='#e1eaf0',width=2)
        y=y0+(y1-y0)*k/6;d.line((x0,y,x1,y),fill='#e1eaf0',width=2)
    d.rectangle((x0,y0,x1,y1),outline='#b4cbdc',width=2)
    for segment in g['actual']:
        if len(segment)>=2:d.line([xy(p) for p in segment],fill='#33946c',width=5,joint='curve')
    if len(g['planned'])>=2:d.line([xy(p) for p in g['planned']],fill='#176eae',width=5,joint='curve')
    for i,p in enumerate(g['planned']):
        x,y=xy(p);d.ellipse((x-3,y-3,x+3,y+3),fill='#176eae')
        if i==0 or i==len(g['planned'])-1 or (len(g['planned'])<30 and i%4==0):
            d.text((x+9,y-18),p.get('name',''),fill='#345773')
    # Separate overlapped label boxes only; marker dots stay exactly at GPS.
    count={}
    for e in g['events']:
        x,y=xy(e);k=(int(x/45),int(y/30));j=count.get(k,0);count[k]=j+1
        d.line((x,y,x+14+12*(j%3),y-18-20*(j//3)),fill='#9e3e36',width=2)
        d.ellipse((x-7,y-7,x+7,y+7),fill='#be5443',outline='white',width=2)
        xx=x+14+12*(j%3);yy=y-18-20*(j//3)
        lab=e['label'];d.rounded_rectangle((xx,yy-4,xx+44,yy+17),radius=5,fill='#ffe7df',outline='#ab594b',width=2)
        d.text((xx+5,yy),lab,fill='#6e271d')
    d.text((75,height-49),'Blue: SimBrief planned route   Green: recorded GPS track   Red: evidence event (true GPS position)',fill='#294e66')
    d.text((75,height-28),'Offline coordinate plot; GPS gaps and implausible track jumps are intentionally disconnected. No underlying terrain imagery.',fill='#63798c')
    b=io.BytesIO();im.save(b,format='PNG');return b.getvalue()
