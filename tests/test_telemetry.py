# SPDX-License-Identifier: AGPL-3.0-only
import csv, io, json, tempfile, threading, unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from telemetry_store import TelemetryStore, FIELDS
from simbridge import Bridge


class TelemetryTests(unittest.TestCase):
    def test_5_second_cadence_no_simbrief_and_separate_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=TelemetryStore(Path(tmp)/'flight_telemetry_5s.csv')
            state={'tracking_enabled':True,'route_fixes':[],'samples':[],'telemetry':[]}
            def load():return json.loads(json.dumps(state))
            def save(v):state.update(v)
            b=Bridge(load,save,threading.RLock(),store)
            d={'fob_kg':10000,'ff1_kg_h':2500,'ff2_kg_h':2550,
               'ff_total_kg_h':5050,'lat':48.67,'lon':9.2,
               'altitude_ft':33000,'vertical_speed_fpm':1200,
               'wind_from_deg':210,'wind_speed_kt':62,'ias_kt':285,
               'tas_kt':470,'groundspeed_kt':512,'mach':.83,'on_ground':0}
            with patch('simbridge.time.monotonic',side_effect=[1,3.5,6.1]),patch('simbridge.time.time',side_effect=[1000,1002.5,1005.1]):
                b._record(d)
                b._record({**d,'fob_kg':9998})
                b._record({**d,'fob_kg':9988})
            self.assertEqual(store.count,2)
            self.assertEqual(len(state['samples']),0)
            rows=list(csv.DictReader(io.StringIO(store.data().decode('utf-8-sig'))))
            self.assertEqual(len(rows),2)
            self.assertEqual(rows[-1]['total_ff_kg_h'],'5050.0')
            self.assertEqual(rows[-1]['phase_estimate'],'CLIMB')
            self.assertEqual(rows[-1]['wind_speed_kt'],'62.0')
            self.assertEqual(rows[-1]['fob_delta_previous_kg'],'12.0')
            self.assertEqual(rows[-1]['quality_flag'],'OK')
            self.assertEqual(rows[-1]['derived_fob_burn_kg_h'],'8470.59')
            self.assertEqual(TelemetryStore(store.path).count,2)

    def test_sample_gap_refueling_and_missing_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'full.csv';db=TelemetryStore(p)
            db.append({'fob_kg':8500,'ff1_kg_h':2700,'on_ground':0,'vertical_speed_fpm':-800},2000)
            db.append({'fob_kg':8600,'ff1_kg_h':None,'on_ground':1,'vertical_speed_fpm':0},2005)
            db.append({'fob_kg':8550,'on_ground':0,'vertical_speed_fpm':-500},2030)
            rows=db.recent()
            self.assertEqual(rows[1]['quality_flag'],'FOB_INCREASE_REFUEL_OR_RESET')
            self.assertEqual(rows[2]['quality_flag'],'SAMPLE_GAP')
            self.assertEqual(rows[1]['phase_estimate'],'GROUND')
            self.assertEqual(rows[0]['phase_estimate'],'DESCENT')
            self.assertEqual(rows[1]['engine1_ff_kg_h'],'')
            self.assertEqual(list(rows[-1]),FIELDS)

if __name__=='__main__':unittest.main()
