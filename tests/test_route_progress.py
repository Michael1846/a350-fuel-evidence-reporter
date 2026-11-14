# SPDX-License-Identifier: AGPL-3.0-only
import threading, unittest, json, sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from simbridge import Bridge

class RouteProgressTests(unittest.TestCase):
  def test_direct_to_skips_four_points_and_matches_ahead(self):
    points=[{'ident':f'WP{i}', 'lat':48+i*.12,'lon':9+i*.12,'planned_kg':10000-i*110} for i in range(8)]
    state={'tracking_enabled':True,'samples':[],'route_fixes':points,'telemetry':[]}
    def load():return json.loads(json.dumps(state))
    def save(x):state.update(x)
    b=Bridge(load,save,threading.RLock())
    with patch('simbridge.time.monotonic',side_effect=[10,17]),patch('simbridge.time.time',side_effect=[1000,1007]):
      b._record({'fob_kg':10001,'engine1_combustion':1,'lat':points[0]['lat'],'lon':points[0]['lon']})
      b._record({'fob_kg':9500,'engine1_combustion':1,'lat':points[6]['lat'],'lon':points[6]['lon']})
    self.assertEqual([x['ident'] for x in state['samples']],['WP0','WP6'])
    self.assertEqual([x['ident'] for x in state['skipped_waypoints']],['WP1','WP2','WP3','WP4','WP5'])
    self.assertEqual(state['samples'][-1]['actual_kg'],9500)
  def test_missing_fob_does_not_fabricate_checkpoint(self):
    state={'tracking_enabled':True,'samples':[],'route_fixes':[{'ident':'WP','lat':48,'lon':9,'planned_kg':5000}],'telemetry':[]}
    b=Bridge(lambda:json.loads(json.dumps(state)),lambda x:state.update(x),threading.RLock())
    with patch('simbridge.time.monotonic',return_value=1),patch('simbridge.time.time',return_value=1000):
      b._record({'fob_kg':None,'lat':48,'lon':9,'ff1_kg_h':2500})
    self.assertEqual(state['samples'],[])
    self.assertEqual(state['telemetry'][0]['ff1_kg_h'],2500)

if __name__=='__main__':unittest.main()
