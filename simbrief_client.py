# SPDX-License-Identifier: AGPL-3.0-only
"""SimBrief latest OFP fetch and normalized route extraction.
Only invoked by an explicit Import button; never polled.
"""
import json
from urllib.request import Request, urlopen
from urllib.parse import urlencode, urljoin, urlparse

USER_AGENT = 'A350FuelEvidenceReporter/0.2 (SimBriefOFPLoader)'
KG_PER_LB = 0.45359237


def num(value):
    try:
        if value is None or str(value).strip() == '': return None
        return float(value)
    except (ValueError, TypeError): return None


def get(obj, *keys, default=None):
    for key in keys:
        if not isinstance(obj, dict): return default
        obj=obj.get(key)
    return obj if obj is not None else default


def normalize_ofp(payload):
    if not isinstance(payload, dict): raise ValueError('Invalid SimBrief OFP response')
    fetch=payload.get('fetch') or {}
    if isinstance(fetch,dict) and fetch.get('status') and str(fetch.get('status')).lower() != 'success':
        raise ValueError('SimBrief: '+str(fetch.get('status'))[:200])
    factor=KG_PER_LB if str(get(payload,'params','units',default='kgs')).lower() in ('lbs','lb') else 1.0
    def kg(x):
        value=num(x)
        return round(value*factor,2) if value is not None else None
    fuel=payload.get('fuel') or {}
    gen=payload.get('general') or {}
    atc=payload.get('atc') or {}
    nav=payload.get('navlog') or {}
    if isinstance(nav,dict): nav=nav.get('fix') or []
    if isinstance(nav,dict): nav=[nav]
    route=[]
    for item in nav if isinstance(nav,list) else []:
        if not isinstance(item,dict): continue
        lat=num(item.get('pos_lat'));lon=num(item.get('pos_long'))
        if lat is None or lon is None or abs(lat)>90 or abs(lon)>180:continue
        route.append({'ident':str(item.get('ident') or item.get('name') or f'FIX{len(route)+1}')[:32],
            'lat':lat,'lon':lon,'phase':str(item.get('stage') or ''),
            'planned_kg':kg(item.get('fuel_plan_onboard')), 'type':str(item.get('type') or ''),
            'index':len(route)})
    trip=kg(fuel.get('enroute_burn'))
    takeoff=kg(fuel.get('plan_takeoff'))
    landing=kg(fuel.get('plan_landing'))
    if landing is None and takeoff is not None and trip is not None:landing=round(takeoff-trip,2)
    callsign=str(atc.get('callsign') or gen.get('flight_number') or '')
    orig=str(get(payload,'origin','icao_code') or get(payload,'origin','icao') or '')
    dest=str(get(payload,'destination','icao_code') or get(payload,'destination','icao') or '')
    summary={
      'flight':callsign,'dep':orig,'arr':dest,
      'ofp_block_kg':kg(fuel.get('plan_ramp')),'ofp_takeoff_kg':takeoff,
      'ofp_trip_kg':trip,'ofp_dest_efob_kg':landing,
      'cost_index':gen.get('costindex') or gen.get('cost_index') or '',
    }
    # PDF file path is supplied by SimBrief, but only fetch from simbrief.com origins.
    files=payload.get('files') or payload.get('fms_downloads') or {}
    pdf=files.get('pdf') or {}
    link=pdf.get('link') if isinstance(pdf,dict) else str(pdf)
    directory=files.get('directory') or ''
    url=urljoin(str(directory),str(link)) if link else None
    if url:
        parsed=urlparse(url)
        if parsed.scheme!='https' or not (parsed.hostname=='simbrief.com' or str(parsed.hostname).endswith('.simbrief.com')):
            url=None
    return {'meta':summary,'route_fixes':route,'pdf_url':url,'units':str(get(payload,'params','units',default='kgs')),
            'navlog_count':len(route),'ofp_time':get(payload,'params','time_generated',default='')}


def fetch_latest(user_id):
    user_id=str(user_id or '').strip()
    if not user_id.isdigit() or not 1<=len(user_id)<=9: raise ValueError('Enter a numeric SimBrief Pilot ID')
    url='https://www.simbrief.com/api/xml.fetcher.php?'+urlencode({'userid':user_id,'client':'a350_fuel_evidence_reporter_0.2','json':'v2'})
    req=Request(url,headers={'User-Agent':USER_AGENT,'Accept':'application/json'})
    with urlopen(req,timeout=16) as r:
        data=r.read(5_000_001)
    if len(data)>5_000_000:raise ValueError('SimBrief response too large')
    return normalize_ofp(json.loads(data.decode('utf-8-sig')))


def download_pdf(url):
    p=urlparse(url)
    if p.scheme!='https' or not (p.hostname=='simbrief.com' or str(p.hostname).endswith('.simbrief.com')):
        raise ValueError('OFP PDF URL is not a SimBrief HTTPS URL')
    req=Request(url,headers={'User-Agent':USER_AGENT})
    with urlopen(req,timeout=22) as r: raw=r.read(15_000_001)
    if len(raw)>15_000_000 or not raw.startswith(b'%PDF'):raise ValueError('SimBrief PDF missing/invalid/too large')
    return raw
