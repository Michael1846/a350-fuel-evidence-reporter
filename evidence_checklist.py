# SPDX-License-Identifier: AGPL-3.0-only
"""Evidence checklist derived from recorded data, not manually claimed completion.

Requirements reflect iniBuilds fuel-issue request pasted by user, plus the user's
explicit preflight screenshot requirement. No simulator data is fabricated.
"""

from datetime import datetime
from evidence_groups import evidence_audit

ISSUE_TYPES = {
    'ground_efob': 'Inaccurate Dest EFOB – on ground',
    'enroute_efob': 'Fluctuations in Dest EFOB – enroute',
    'excessive_burn': 'Excessive Fuel Burn',
}
STAGES = [
    ('preflight', '01 · Before pushback / takeoff'),
    ('enroute', '02 · During flight / when issues occur'),
    ('arrival', '03 · After landing'),
    ('export', '04 · Report & attachments'),
]

def checklist(state, telemetry_count=0):
    m=state.get('meta') or {}
    snapshots=state.get('snapshots') or []
    images=state.get('evidence') or []
    types=[t for t in state.get('case_types', list(ISSUE_TYPES)) if t in ISSUE_TYPES]
    selected=set(types)
    items=[]
    audit=evidence_audit(state)

    def add(ident,stage,title,done,detail,action,required=True):
        items.append({'id':ident,'stage':stage,'title':title,'done':bool(done),'detail':detail,
                      'action':action,'required':required})
    def ss(phase,field):
        return any(s.get('phase')==phase and str(s.get(field,'')).strip()!='' for s in snapshots)
    def any_enroute(field):
        return any(s.get('phase') in ('Climb','Cruise','Descent') and str(s.get(field,'')).strip() for s in snapshots)
    def img(purpose, phases=None):
        return any(s.get('purpose')==purpose and (phases is None or s.get('phase') in phases) for s in images)
    def snapshot_by_issue(issue):
        return [s for s in snapshots if s.get('issue_type')==issue]
    def linked_img(purpose, ids):
        return any(s.get('purpose')==purpose and s.get('observation_id') in ids for s in images)

    def preflight_img_valid(ev):
        if ev.get('purpose')!='preflight_prediction' or ev.get('phase') not in ('Pushback','Preflight'):return False
        cx=ev.get('context') or {}
        # Positively known airborne capture does not satisfy the preflight item.
        if cx.get('flight_status') in ('AIRBORNE','LANDED'):return False
        takeoff=state.get('first_airborne_utc_unix')
        if takeoff and cx.get('event_time_utc'):
            try:
                captured=datetime.fromisoformat(cx['event_time_utc'].replace('Z','+00:00')).timestamp()
                return captured< float(takeoff)
            except (ValueError,TypeError):pass
        return True  # uploaded file: present, but time unverifiable.
    preflight_images=[ev for ev in images if preflight_img_valid(ev)]
    verified_preflight=any((ev.get('context') or {}).get('flight_status')=='GROUND' and ev.get('capture_source')=='app_capture' for ev in preflight_images)
    def status_in_groups(issue,field,old_value):
        members=[a for a in audit if a['issue_type']==issue]
        if not members:return old_value
        return any(any(f['id']==field and f['done'] for f in g['requirements']) for g in members)

    add('issue_type','preflight','Issue category selected',bool(types),
        'Select at least one of the three iniBuilds fuel issue categories.','workflow')
    add('aircraft','preflight','Simulator, A350 variant and build documented',
        bool(m.get('sim') and m.get('variant') and m.get('version')),
        'Use the version detected from the local package or enter it manually.','flight')
    add('live','preflight','Live Time and Live Weather enabled',
        m.get('live_time')=='Yes' and m.get('live_weather')=='Yes',
        'Check both simulator settings and confirm with Yes.','flight')
    add('ofp','preflight','SimBrief OFP PDF attached',bool(state.get('ofp')),
        'Import using SimBrief user ID or upload the OFP as PDF.','flight')
    add('preflight_img','preflight','Preflight FMS fuel prediction screenshot',bool(preflight_images),
        'Capture FMS FUEL & LOAD / destination EFOB before pushback. Capture timing: '+('SimConnect confirms aircraft on ground' if verified_preflight else 'Not independently verified – verify capture time')+'.','preflight_capture')

    if 'ground_efob' in selected:
        add('sb_dest','preflight','SimBrief Destination EFOB (kg)',str(m.get('ofp_dest_efob_kg','')).strip()!='',
            'Import OFP destination EFOB from SimBrief or enter it.','flight')
        add('pushback','preflight','FMS destination EFOB at pushback (kg)',ss('Pushback','fms_efob_kg'),
            'Read FMS EFOB manually and save as a pushback observation.','pushback_event')
        add('landing','arrival','Actual FOB when vacating runway (kg)',ss('Runway vacated','actual_fob_kg'),
            'Record FOB when vacating the runway, not after reaching the gate.','landing_event')

    if 'enroute_efob' in selected:
        add('enroute_value','enroute','FMS destination EFOB during fluctuation',status_in_groups('enroute_efob','fms_value',any_enroute('fms_efob_kg')),
            'Record FMS EFOB manually with flight phase and UTC time.','enroute_event')
        add('enroute_fms','enroute','FMS FUEL & LOAD page screenshot',status_in_groups('enroute_efob','fms_screen',img('fms_fuel_load',('Climb','Cruise','Descent'))),
            'Capture and link a screenshot during the EFOB fluctuation.','enroute_capture')
        add('enroute_ff','enroute','Current fuel flow screenshot (both engines)',status_in_groups('enroute_efob','engine_ff_screen',img('engine_ff',('Climb','Cruise','Descent'))),
            'Capture the engine fuel-flow indication for the same event.','ff_capture')
        add('enroute_bin','enroute','OIS autosave (.bin) for this event',status_in_groups('enroute_efob','ois_autosave',bool(state.get('bin') or state.get('autosaves'))),
            'For the event, select OIS: FLT OPS MENU → AUTOSAVE → SAVE NOW, then upload the .bin.','bin_capture')

    if 'excessive_burn' in selected:
        burn=snapshot_by_issue('excessive_burn')
        ids={s.get('id') for s in burn}
        add('burn_event','enroute','Fuel-flow issue with flight phase and description',
            any(s.get('note','').strip() and (str(s.get('ff1_kg_h','')).strip() or str(s.get('ff2_kg_h','')).strip()) for s in burn),
            'Record the issue as “Excessive Fuel Burn”, including fuel-flow values and description.','burn_event')
        add('burn_ff_img','enroute','Fuel-flow screenshot for the recorded event',linked_img('engine_ff',ids),
            'Link a fuel-flow screenshot to the recorded excessive fuel burn event.','burn_capture')
        add('burn_fms_img','enroute','FMS FUEL & LOAD screenshot for this event',linked_img('fms_fuel_load',ids),
            'Link the FMS screenshot to the same issue.','burn_fms_capture')
        if 'enroute_efob' not in selected:
            add('burn_bin','enroute','OIS autosave (.bin) for this event',status_in_groups('excessive_burn','ois_autosave',bool(state.get('bin') or state.get('autosaves'))),
                'Select SAVE NOW during the event and upload the .bin later.','bin_capture')

    add('waypoints','export','Waypoint fuel checkpoints',bool(state.get('samples')),
        'Generated from SimBrief route and GPS measurements (additional analytical evidence).','fuel',False)
    add('telemetry','export','Continuous 5-second telemetry',telemetry_count>0,
        'Recording starts after SimConnect connection; additional evidence, not an iniBuilds-required attachment.','telemetry',False)
    required=[x for x in items if x['required']]
    return {'issue_types':types,'issues':[{'id':v,'title':ISSUE_TYPES[v]} for v in types],
            'stages':[{'id':sid,'title':title,'items':[x for x in items if x['stage']==sid]} for sid,title in STAGES],
            'total':len(required),'complete':sum(x['done'] for x in required),
            'remaining':sum(not x['done'] for x in required),
            'ready':len(required)>0 and all(x['done'] for x in required),
            'export_allowed':True,'missing_items_are_warnings':True,'event_groups':audit}
