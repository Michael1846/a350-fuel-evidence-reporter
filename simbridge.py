# SPDX-License-Identifier: AGPL-3.0-only
"""Best-effort Windows SimConnect bridge. Read-only. Never modifies simulator state.

The default SimVars are documented by Microsoft, but specific add-on mapping
must be validated against aircraft cockpit fuel indications.
"""
import math, threading, time
from aircraft_identity import as_text, detect_variant, simulator_process, package_version
from engine_fuel_reader import EngineFuelReader, IniBuildsFuelFlowProbe
from engine_antiice_reader import EngineAntiIceReader
from aircraft_engine_adapter import AircraftEngineAdapter
from datetime import datetime, timezone

KG_PER_LB=0.45359237


def haversine_nm(a,b,c,d):
    p1,p2=math.radians(float(a)),math.radians(float(c))
    dp=math.radians(float(c)-float(a));dl=math.radians(float(d)-float(b))
    v=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 3440.065*2*math.asin(min(1,math.sqrt(v)))


def reading(v):
    try:
        if v is None:return None
        x=float(v)
        return x if math.isfinite(x) else None
    except (TypeError,ValueError):return None


class Bridge:
    def __init__(self,load_state,save_state,lock,telemetry_store=None,engine_profile_path=None):
        self.load_state=load_state;self.save_state=save_state;self.lock=lock
        self.telemetry_store=telemetry_store
        self.engine_profile_path=engine_profile_path
        self.status={'state':'disconnected','message':'SimConnect not yet connected', 'timestamp':None,'data':{}}
        self._stop=threading.Event();self._thread=None
        self._last_saved=0;self._last_obs=0;self._matched=set()
        self._last_telemetry_mono=-1e12
        self._identity_checked=0;self._identity_title='';self._identity={}
        self._airborne_seen=False;self._was_on_ground=None;self._flight_status='UNKNOWN'
        self._engines_running=False;self._engine_off_streak=0;self._engine_detection='UNKNOWN'
        self._recording_state='WAITING_FOR_ENGINES'

    def start(self):
        if self._thread and self._thread.is_alive():
            if self._stop.is_set():self._thread.join(timeout=4.0)
            if self._thread.is_alive():return
        self._stop.clear()
        self._thread=threading.Thread(target=self._work,name='simconnect-evidence-reader',daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._engines_running=False;self._engine_off_streak=0
        self._recording_state='DISCONNECTED'
        if self.telemetry_store:self.telemetry_store.break_interval()
        self._set('disconnected','Connection stopped by user')

    def reset_session(self):
        self._last_telemetry_mono=-1e12
        self._identity_checked=0;self._identity_title='';self._identity={}
        self._airborne_seen=False;self._was_on_ground=None;self._flight_status='UNKNOWN'
        self._engines_running=False;self._engine_off_streak=0;self._engine_detection='UNKNOWN'
        self._recording_state='WAITING_FOR_ENGINES'
        if self.telemetry_store:self.telemetry_store.break_interval()

    def _set(self,state,message='',snapshot=None):
        self.status={'state':state,'message':message,'timestamp':time.time(),'data':snapshot or {},
                     'telemetry_count':self.telemetry_store.count if self.telemetry_store else 0,
                     'identity':self._identity,'flight_status':self._flight_status,
                     'engines_running':self._engines_running,
                     'engine_detection':self._engine_detection,
                     'recording_state':self._recording_state,
                     'availability':self._availability(snapshot or {})}

    @staticmethod
    def _availability(d):
        keys={'Fuel on Board':'fob_kg','Engine 1 Fuel Flow':'ff1_kg_h',
              'Engine 2 Fuel Flow':'ff2_kg_h','Latitude':'lat','Longitude':'lon',
              'Altitude':'altitude_ft','IAS':'ias_kt','TAS':'tas_kt',
              'Ground Speed':'groundspeed_kt','Vertical Speed':'vertical_speed_fpm',
              'Wind Speed':'wind_speed_kt','Wind Direction':'wind_from_deg',
              'N1 Engine 1':'engine1_n1_pct','N1 Engine 2':'engine2_n1_pct',
              'Engine 1 Combustion':'engine1_combustion','Engine 2 Combustion':'engine2_combustion',
              'Engine 1 Anti-Ice':'engine1_antiice','Engine 2 Anti-Ice':'engine2_antiice',
              'Total Weight':'total_weight_kg','Outside Temperature':'oat_c'}
        return {label:('readable' if d.get(key) is not None else 'missing') for label,key in keys.items()}

    def _capture_identity(self,aq):
        # RequestList exposes these standard STRING SimVars via AircraftRequests.
        def get_text(k):
            try:return as_text(aq.get(k))
            except Exception:return ''
        title=get_text('TITLE');model=get_text('ATC_MODEL');typ=get_text('ATC_TYPE')
        if not (title or model or typ):return
        variant=detect_variant(title,model,typ)
        changed=bool(self._identity_title and title and title!=self._identity_title)
        if changed:
            with self.lock:
                state=self.load_state();state['tracking_enabled']=False
                self.save_state(state)
        if not variant['family']:
            self._identity={'title':title,'model':model,'type':typ,'variant':'',
                            'version':'','version_status':'not_applicable','sim':simulator_process()}
            if changed:self._identity['warning']='Aircraft changed: tracking paused to avoid mixing flights'
            self._identity_title=title
            return
        pkg=package_version(variant['family'])
        sim=simulator_process()
        identity={'title':title,'model':model,'type':typ,**variant,
                  'version':pkg['version'],'version_status':pkg['status'],
                  'sim':sim,'manifest_candidates':len(pkg['candidates'])}
        if changed:
            identity['warning']='Aircraft changed: tracking paused to avoid mixing flights'
        self._identity_title=title
        self._identity=identity
        with self.lock:
            state=self.load_state();meta=state['meta']
            if variant['variant']:meta['variant']=variant['variant']
            if variant['cabin']:meta['cabin']=variant['cabin']
            if pkg['version']:
                meta['version']=pkg['version']
                meta['version_source']='Local manifest candidate - check in simulator'
            if sim in ('MSFS 2024','MSFS 2020'):meta['sim']=sim
            meta['aircraft_title']=title
            self.save_state(state)

    def _update_flight_status(self,d):
        g=d.get('on_ground')
        if g is None:return
        grounded=bool(g>=0.5)
        if not grounded:
            self._airborne_seen=True;self._flight_status='AIRBORNE'
        elif self._airborne_seen:self._flight_status='LANDED'
        else:self._flight_status='GROUND'
        self._was_on_ground=grounded

    @staticmethod
    def engine_status(data):
        """Conservative engine state detection; no N1-only start (windmilling).

        Combustion flags are preferred; measured fuel flow is used to accommodate
        add-on aircraft that fail to populate the standard combustion SimVars.
        Never interpret missing values as zero or assume engines stopped.
        """
        ff=[reading(data.get(k)) for k in ('ff1_kg_h','ff2_kg_h')]
        combustion=[reading(data.get(k)) for k in ('engine1_combustion','engine2_combustion')]
        if any(v is not None and v > 75.0 for v in ff):
            return 'RUNNING', 'fuel_flow' if not any(v is not None and v>=0.5 for v in combustion) else 'combustion_and_fuel_flow'
        if any(v is not None and v>=0.5 for v in combustion):
            return 'RUNNING', 'combustion'
        # A transition through low but non-zero FF must not flap the status.
        if any(v is not None and v>20.0 for v in ff):
            return 'UNKNOWN', 'spool_transition'
        if any(v is not None for v in combustion+ff):
            return 'STOPPED', 'combustion_or_fuel_flow'
        return 'UNKNOWN', 'no_valid_engine_signal'

    def _update_engine_gate(self, data):
        detected,source=self.engine_status(data)
        self._engine_detection=detected+' ('+source+')'
        if detected=='RUNNING':
            self._engine_off_streak=0
            self._engines_running=True
        elif detected=='STOPPED':
            self._engine_off_streak+=1
            # Two consistent reads (~2.5-5 s) prevent one-sample dropouts.
            if self._engine_off_streak>=2 and self._engines_running:
                self._engines_running=False
                self._last_telemetry_mono=-1e12
                if self.telemetry_store:self.telemetry_store.break_interval()
        else:
            self._engine_off_streak=0
        return self._engines_running

    def _work(self):
        try:
            from SimConnect import SimConnect, AircraftRequests
        except Exception as exc:
            self._set('dependency_missing','SimConnect Python package unavailable: '+str(exc));return
        while not self._stop.is_set():
            sm=None
            try:
                self._set('connecting','Connecting to Microsoft Flight Simulator...')
                sm=SimConnect()
                aq=AircraftRequests(sm,_time=1000)
                adapter=AircraftEngineAdapter(sm,self.engine_profile_path) if self.engine_profile_path else None
                # Read iniBuilds candidate identifiers as raw, unitless probes.
                # These are never silently converted into FF1/FF2.
                ini_probe=IniBuildsFuelFlowProbe(sm)
                engine_reader=EngineFuelReader(sm,aircraft_adapter=adapter,ini_probe=ini_probe)
                antiice_reader=EngineAntiIceReader(sm)
                self.reset_session()
                self._set('connected','SimConnect active')
                while not self._stop.is_set() and not getattr(sm,'quit',False):
                    if time.monotonic()-self._identity_checked>=30:
                        self._capture_identity(aq)
                        self._identity_checked=time.monotonic()
                    def get(var):
                        try:return reading(aq.get(var))
                        except Exception:return None
                    fob_lbs=get('FUEL_TOTAL_QUANTITY_WEIGHT')
                    if fob_lbs is None: fob_lbs=get('FUEL_TOTAL_QUANTITY_WEIGHT_EX1')
                    # Independent pinned engine requests: no index-switching
                    # request redefinition. Both PPH sources are sampled; a
                    # zero from one never masks a positive value from another.
                    fuel_density=get('FUEL_WEIGHT_PER_GALLON')
                    engine_readings=engine_reader.sample(density_lb_gal=fuel_density)
                    antiice_readings=antiice_reader.sample(
                        is_inibuilds_a350=(self._identity.get('family')=='A350'))
                    data={'fob_kg':round(fob_lbs*KG_PER_LB,2) if fob_lbs is not None else None,
                          **engine_readings,
                          **antiice_readings,
                          'lat':get('PLANE_LATITUDE'),'lon':get('PLANE_LONGITUDE'),
                          'altitude_ft':get('PLANE_ALTITUDE'),'groundspeed_kt':get('GROUND_VELOCITY'),
                          'on_ground':get('SIM_ON_GROUND'), 'vertical_speed_fpm':get('VERTICAL_SPEED'),
                          'ias_kt':get('AIRSPEED_INDICATED'),'tas_kt':get('AIRSPEED_TRUE'),
                          'mach':get('AIRSPEED_MACH'),'true_track_deg':get('GPS_GROUND_TRUE_TRACK'),
                          'wind_from_deg':get('AMBIENT_WIND_DIRECTION'),
                          'wind_speed_kt':get('AMBIENT_WIND_VELOCITY'),
                          'oat_c':get('AMBIENT_TEMPERATURE'),
                          'tat_c':get('TOTAL_AIR_TEMPERATURE'),
                          'total_weight_kg':(lambda v:v*KG_PER_LB if v is not None else None)(get('TOTAL_WEIGHT')),
                                                    'structural_deice':get('STRUCTURAL_DEICE_SWITCH'),
                          'sim_zulu_seconds':get('ZULU_TIME'),'sim_rate':get('SIMULATION_RATE'),
                          'source':'SimConnect standard SimVars (aircraft-dependent validation required)'}
                    self._update_flight_status(data)
                    self._record(data)
                    self._set('connected','Live sim data',data)
                    self._stop.wait(2.5)
                self._engines_running=False
                self._recording_state='DISCONNECTED'
                if self.telemetry_store:self.telemetry_store.break_interval()
                self._set('disconnected','Simulator disconnected')
            except Exception as exc:
                self._engines_running=False
                self._recording_state='DISCONNECTED'
                if self.telemetry_store:self.telemetry_store.break_interval()
                self._set('disconnected',str(exc)[:200])
            finally:
                try:
                    if sm is not None:sm.exit()
                except Exception:pass
            self._stop.wait(8)

    def _record(self,data):
        now=time.time()
        if not any(data.get(k) is not None for k in ('fob_kg','ff1_kg_h','ff2_kg_h','lat','altitude_ft','engine1_combustion','engine2_combustion')):return
        with self.lock:
            state=self.load_state()
            active=self._update_engine_gate(data)
            if not state.get('tracking_enabled',False):
                self._recording_state='MANUALLY_PAUSED'
                self._last_telemetry_mono=-1e12
                if self.telemetry_store:self.telemetry_store.break_interval()
                return
            if not active:
                self._recording_state='WAITING_FOR_ENGINES' if self._engine_detection.startswith('UNKNOWN') and self._engine_off_streak==0 else 'ENGINES_OFF'
                return
            # Do not write any new sample while a potential engine shutdown is
            # being confirmed (two consecutive stopped readings).
            if self._engine_detection.startswith('STOPPED'):
                self._recording_state='VERIFYING_SHUTDOWN'
                return
            self._recording_state='RECORDING' if self._engine_detection.startswith('RUNNING') else 'ENGINE_SIGNAL_UNAVAILABLE'
            changed=False
            # Earliest recorded airborne sample bounds preflight proof timing.
            if data.get('on_ground') is not None and float(data['on_ground']) < 0.5 and not state.get('first_airborne_utc_unix'):
                state['first_airborne_utc_unix']=round(now,2)
                changed=True
            # Independent fixed-cadence collection, even if SimBrief is not loaded.
            # Monotonic clock avoids wall clock adjustments changing sampling cadence.
            mono=time.monotonic()
            if mono-self._last_telemetry_mono>=5.0:
                if self.telemetry_store:
                    self.telemetry_store.append(data,now)
                else:  # compatibility for in-memory tests
                    state.setdefault('telemetry',[]).append({'timestamp':round(now,2),**data})
                    state['telemetry']=state['telemetry'][-500:]
                    changed=True
                self._last_telemetry_mono=mono
            lat,lon=data.get('lat'),data.get('lon')
            if lat is not None and lon is not None and data.get('fob_kg') is not None:
                fixes=state.get('route_fixes') or []
                matched={int(r['waypoint_idx']) for r in state.get('samples',[]) if r.get('source')=='simconnect' and r.get('waypoint_idx') is not None}
                current=max(matched)+1 if matched else 0
                # Search all *forward* route fixes. Direct-to / late session start
                # must not block later checkpoints behind an unmatched fix.
                # A checkpoint is recorded only on actual GPS proximity.
                options=[]
                for index in range(current,len(fixes)):
                    if index in matched:continue
                    wp=fixes[index]
                    dist=haversine_nm(lat,lon,wp['lat'],wp['lon'])
                    if dist<=1.5:options.append((dist,index,wp))
                if options:
                    dist,index,wp=min(options)
                    if index>current:
                        state.setdefault('skipped_waypoints',[])
                        already={entry.get('index') for entry in state['skipped_waypoints']}
                        for skipped in range(current,index):
                            if skipped not in already:
                                state['skipped_waypoints'].append({'index':skipped,'ident':fixes[skipped]['ident'],'reason':'Not observed within GPS threshold'})
                    actual=data['fob_kg'];planned=wp.get('planned_kg')
                    obs={'ident':wp['ident'],'timestamp':round(now,2),'actual_kg':round(actual,2),
                         'planned_kg':planned,'delta_kg':round(actual-planned,2) if planned is not None else None,
                         'distance_nm':round(dist,3),'waypoint_idx':index,'check_type':'WAYPOINT',
                         'source':'simconnect','phase':wp.get('phase'),'lat':lat,'lon':lon,
                         'altitude_ft':data.get('altitude_ft'),'ff1_kg_h':data.get('ff1_kg_h'),
                         'ff2_kg_h':data.get('ff2_kg_h'),
                         'engine1_antiice':data.get('engine1_antiice'),
                         'engine2_antiice':data.get('engine2_antiice')}
                    state['samples'].append(obs)
                    state['samples']=sorted(state['samples'],key=lambda a:a['timestamp'])
                    changed=True
            if changed:self.save_state(state)
