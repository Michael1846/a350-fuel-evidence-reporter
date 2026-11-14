# SPDX-License-Identifier: AGPL-3.0-only
"""Engine-based automatic telemetry start and stop, without requiring SimBrief."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from simbridge import Bridge
from telemetry_store import TelemetryStore

class EngineTelemetryGateTests(unittest.TestCase):
    def new(self, root):
        state={'tracking_enabled':True,'route_fixes':[],'samples':[],'telemetry':[]}
        store=TelemetryStore(root/'flight_telemetry_5s.csv')
        bridge=Bridge(lambda:json.loads(json.dumps(state)),lambda v:state.update(v),threading.RLock(),store)
        return state,store,bridge

    @staticmethod
    def d(ff1=0,ff2=0,c1=0,c2=0,fob=10000):
        return {'fob_kg':fob,'ff1_kg_h':ff1,'ff2_kg_h':ff2,
                'engine1_combustion':c1,'engine2_combustion':c2,
                'lat':48.7,'lon':9.2,'on_ground':1,'altitude_ft':1000}

    def test_wait_start_keep_one_engine_then_stop_both_and_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            state,db,b=self.new(Path(tmp))
            samples=[
                (1000,1,self.d()),             # connect, both engines off
                (1002.5,3.5,self.d(ff1=210,c1=1)), # engine 1 start
                (1007.5,8.5,self.d(ff1=350,ff2=100,c1=1,c2=1,fob=9980)),
                (1012.5,13.5,self.d(ff1=240,c1=1,fob=9970)), # engine 2 off; keep going
                (1017.5,18.5,self.d(fob=9950)), # engines off, first sample
                (1020,21,self.d(fob=9950)),     # engines off, second sample -> stop
                (1030,31,self.d(fob=9950)),     # parked, still no logging
                (1040,41,self.d(ff1=300,c1=1,fob=9930)), # engine restart
            ]
            for ts,mono,data in samples:
                with patch('simbridge.time.time',return_value=ts),patch('simbridge.time.monotonic',return_value=mono):
                    b._record(data)
            self.assertEqual(db.count,4) # 1002.5,1007.5,1012.5,1040; none after both engines stop
            rows=db.recent(10)
            self.assertEqual(float(rows[0]['timestamp_unix']),1002.5)
            self.assertEqual(float(rows[-1]['timestamp_unix']),1040)
            self.assertEqual(rows[-1]['interval_seconds'],'') # no derived rate through shutdown
            self.assertEqual(b._recording_state,'RECORDING')
            self.assertTrue(b._engines_running)

    def test_no_engine_signal_does_not_falsely_start_and_n1_not_sufficient(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,db,b=self.new(Path(tmp))
            for ts,data in [(1,{'fob_kg':10000,'lat':48.7,'engine1_n1_pct':55}),
                            (7,{'fob_kg':9999,'lat':48.7,'ff1_kg_h':0,'ff2_kg_h':0}),
                            (12,{'fob_kg':9999,'lat':48.7,'ff1_kg_h':180,'ff2_kg_h':0})]:
                with patch('simbridge.time.time',return_value=ts),patch('simbridge.time.monotonic',return_value=ts):
                    b._record(data)
            self.assertEqual(db.count,1)
            self.assertEqual(b._recording_state,'RECORDING')
            self.assertEqual(float(db.recent()[0]['timestamp_unix']),12)

    def test_manual_pause_and_rearm_do_not_override_off_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            state,db,b=self.new(Path(tmp))
            for t,d in [(10,self.d(ff1=250,c1=1)),(15,self.d()) ,(20,self.d())]:
                if t==15:state['tracking_enabled']=False
                with patch('simbridge.time.time',return_value=t),patch('simbridge.time.monotonic',return_value=t):b._record(d)
            self.assertEqual(db.count,1)
            self.assertFalse(b._engines_running)
            state['tracking_enabled']=True
            with patch('simbridge.time.time',return_value=25),patch('simbridge.time.monotonic',return_value=25):b._record(self.d())
            self.assertEqual(db.count,1)
            self.assertEqual(b._recording_state,'ENGINES_OFF')

    def test_fuel_flow_fallback_with_missing_combustion(self):
        self.assertEqual(Bridge.engine_status({'ff1_kg_h':2300,'ff2_kg_h':0})[0],'RUNNING')
        self.assertEqual(Bridge.engine_status({'ff1_kg_h':0,'ff2_kg_h':0})[0],'STOPPED')
        self.assertEqual(Bridge.engine_status({'ff1_kg_h':None,'ff2_kg_h':None})[0],'UNKNOWN')
        self.assertEqual(Bridge.engine_status({'engine1_n1_pct':35})[0],'UNKNOWN')
        self.assertEqual(Bridge.engine_status({'ff1_kg_h':42,'ff2_kg_h':0})[0],'UNKNOWN')

if __name__=='__main__':unittest.main()
