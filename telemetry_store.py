# SPDX-License-Identifier: AGPL-3.0-only
"""Append-only, per-case continuous telemetry file. No pandas/Excel dependency.

Each observation is independently timestamped and persisted to disk immediately;
waypoint detection and SimBrief import are not prerequisites.
"""
import csv
import io
import math
import threading
from datetime import datetime, timezone
from pathlib import Path

FIELDS = [
 'timestamp_unix','timestamp_utc','sim_zulu_seconds','sim_rate','phase_estimate',
 'on_ground','latitude_deg','longitude_deg','altitude_ft','vertical_speed_fpm',
 'ias_kt','tas_kt','groundspeed_kt','mach', 'true_track_deg',
 'wind_from_deg','wind_speed_kt','oat_c','tat_c','total_weight_kg',
 'engine1_n1_pct','engine2_n1_pct','engine1_antiice','engine2_antiice',
 'engine1_antiice_source','engine2_antiice_source','structural_deice',
 'fob_kg','engine1_ff_kg_h','engine2_ff_kg_h','total_ff_kg_h',
 'engine1_ff_source','engine2_ff_source',
 'fob_delta_previous_kg','interval_seconds','derived_fob_burn_kg_h',
 'quality_flag'
]

# Use descriptive, fixed, SI/aviation units in columns. Never represent
# derived FOB slope as engine fuel flow.
KEYS = {
 'sim_zulu_seconds':'sim_zulu_seconds','sim_rate':'sim_rate',
 'on_ground':'on_ground','latitude_deg':'lat','longitude_deg':'lon',
 'altitude_ft':'altitude_ft','vertical_speed_fpm':'vertical_speed_fpm',
 'ias_kt':'ias_kt','tas_kt':'tas_kt','groundspeed_kt':'groundspeed_kt',
 'mach':'mach','true_track_deg':'true_track_deg',
 'wind_from_deg':'wind_from_deg','wind_speed_kt':'wind_speed_kt',
 'oat_c':'oat_c','tat_c':'tat_c','total_weight_kg':'total_weight_kg',
 'engine1_n1_pct':'engine1_n1_pct','engine2_n1_pct':'engine2_n1_pct',
 'engine1_antiice':'engine1_antiice','engine2_antiice':'engine2_antiice',
 'structural_deice':'structural_deice','fob_kg':'fob_kg',
 'engine1_ff_kg_h':'ff1_kg_h','engine2_ff_kg_h':'ff2_kg_h',
 'total_ff_kg_h':'ff_total_kg_h'
}


def phase_for(data):
    if data.get('on_ground') is not None and float(data['on_ground']) >= 0.5:
        return 'GROUND'
    vs = data.get('vertical_speed_fpm')
    if vs is None:return 'UNKNOWN'
    if float(vs) > 300:return 'CLIMB'
    if float(vs) < -300:return 'DESCENT'
    return 'LEVEL'


class TelemetryStore:
    def __init__(self, path):
        self.path=Path(path)
        self._lock=threading.RLock()
        self._prev=None
        self.count=0
        self._migrate_header_if_needed()
        self._restore_tail()

    def _migrate_header_if_needed(self):
        """Upgrade an existing 0.7.4 CSV header without discarding flight data.

        This release adds per-sample FF provenance. For an existing telemetry
        file the old header is expanded *before* writing new records; old rows
        receive empty values for newly introduced fields. Use an atomic replace.
        """
        if not self.path.is_file() or self.path.stat().st_size == 0:
            return
        temporary = self.path.with_suffix('.migrating.tmp')
        try:
            with self.path.open('r', encoding='utf-8-sig', newline='') as source:
                reader = csv.DictReader(source)
                previous = reader.fieldnames or []
                additions = [name for name in FIELDS if name not in previous]
                if not additions:
                    return
                if not set(previous).issubset(FIELDS):
                    # Avoid silently dropping future/unknown column types.
                    raise ValueError('Unsupported telemetry CSV header; refusing destructive migration')
                with temporary.open('w', encoding='utf-8-sig', newline='') as output:
                    writer = csv.DictWriter(output, fieldnames=FIELDS)
                    writer.writeheader()
                    for row in reader:
                        writer.writerow({name: row.get(name, '') for name in FIELDS})
            # Windows cannot replace the destination while our read handle is open.
            temporary.replace(self.path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def _restore_tail(self):
        if not self.path.is_file(): return
        with self._lock, self.path.open('r',encoding='utf-8-sig',newline='') as fh:
            for r in csv.DictReader(fh):
                self.count+=1
                self._prev=r

    def break_interval(self):
        """Do not compute fuel burn across engine-off/paused/disconnected gaps."""
        with self._lock:
            self._prev=None

    @staticmethod
    def _num(v):
        try:
            value=float(v)
            return round(value,4) if math.isfinite(value) else None
        except (TypeError,ValueError):return None

    def append(self, data, timestamp):
        if not any(self._num(data.get(k)) is not None for k in ('fob_kg','ff1_kg_h','ff2_kg_h','lat','altitude_ft')):return None
        with self._lock:
            rec={key:self._num(data.get(src)) for key,src in KEYS.items()}
            # Canonical binary anti-ice state for new CSV rows. Older rows
            # containing 0.0/1.0 remain intact and are accepted by the UI.
            for antiice_key in ('engine1_antiice','engine2_antiice'):
                value=rec[antiice_key]
                rec[antiice_key]=int(value) if value in (0,1) else None
            # Persist the exact per-engine provenance per sample, including
            # dynamically configured LVars; source cannot be inferred later.
            rec['engine1_ff_source']=str(data.get('ff1_source') or '')[:170]
            rec['engine2_ff_source']=str(data.get('ff2_source') or '')[:170]
            rec['engine1_antiice_source']=str(data.get('engine1_antiice_source') or '')[:170]
            rec['engine2_antiice_source']=str(data.get('engine2_antiice_source') or '')[:170]
            rec['timestamp_unix']=round(float(timestamp),3)
            rec['timestamp_utc']=datetime.fromtimestamp(timestamp,timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]+' UTC'
            rec['phase_estimate']=phase_for(data)
            rec['fob_delta_previous_kg']=None
            rec['interval_seconds']=None
            rec['derived_fob_burn_kg_h']=None
            rec['quality_flag']='OK' if rec['fob_kg'] is not None else 'MISSING_FOB'
            prev=self._prev
            if prev:
                elapsed=rec['timestamp_unix']-float(prev['timestamp_unix'])
                previous_fob=self._num(prev.get('fob_kg'))
                rec['interval_seconds']=round(elapsed,3)
                if elapsed>0 and previous_fob is not None and rec['fob_kg'] is not None:
                    delta=round(previous_fob-rec['fob_kg'],4)
                    rec['fob_delta_previous_kg']=delta
                    if delta < -1.0:
                        rec['quality_flag']='FOB_INCREASE_REFUEL_OR_RESET'
                    elif elapsed > 12:
                        rec['quality_flag']='SAMPLE_GAP'
                    elif elapsed >= 4:
                        rec['derived_fob_burn_kg_h']=round(delta*3600/elapsed,2)
                    else:
                        rec['quality_flag']='TOO_SHORT_FOR_RATE'
            rec={key:rec.get(key) for key in FIELDS}
            self.path.parent.mkdir(parents=True,exist_ok=True)
            new=not self.path.exists() or self.path.stat().st_size==0
            with self.path.open('a',encoding='utf-8-sig' if new else 'utf-8',newline='') as fh:
                writer=csv.DictWriter(fh,fieldnames=FIELDS)
                if new:writer.writeheader()
                writer.writerow({k: '' if v is None else v for k,v in rec.items()})
            self._prev=rec
            self.count+=1
            return rec

    def data(self):
        with self._lock:
            return self.path.read_bytes() if self.path.exists() else b''

    def recent(self,limit=20):
        with self._lock:
            if not self.path.is_file():return []
            with self.path.open('r',encoding='utf-8-sig',newline='') as fh:
                rows=list(csv.DictReader(fh))
            return rows[-limit:]

    def profile(self,limit=2200):
        """Entire flight profile, bounded JSON. Preserve extrema within time buckets.

        Full 5-second CSV remains available; this method decimates only the UI.
        """
        limit=max(100,min(int(limit),4000))
        with self._lock:
            if not self.path.is_file():return []
            with self.path.open('r',encoding='utf-8-sig',newline='') as fh:
                rows=list(csv.DictReader(fh))
        if len(rows)<=limit:return rows
        buckets=max(1,(limit-2)//4)
        indices={0,len(rows)-1}
        for bucket in range(buckets):
            start=1+(len(rows)-2)*bucket//buckets
            end=1+(len(rows)-2)*(bucket+1)//buckets
            if start>=end:continue
            indices.add(start)
            for key in ('total_ff_kg_h','altitude_ft','fob_kg'):
                vals=[]
                for i in range(start,end):
                    v=self._num(rows[i].get(key))
                    if v is not None:vals.append((v,i))
                if vals:
                    indices.add(min(vals)[1]);indices.add(max(vals)[1])
        ordered=sorted(indices)
        if len(ordered)>limit:
            stride=(len(ordered)-1)/(limit-1)
            ordered=sorted({ordered[round(k*stride)] for k in range(limit)} | {0,len(rows)-1})
        return [rows[i] for i in ordered]

    def clear(self):
        with self._lock:
            if self.path.is_file():self.path.unlink()
            self.count=0
            self._prev=None
