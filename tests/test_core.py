# SPDX-License-Identifier: AGPL-3.0-only
import io,sys,unittest,threading,zipfile, json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from simbrief_client import normalize_ofp
from simbridge import Bridge,haversine_nm
import app

class ReporterCoreTests(unittest.TestCase):
  def test_simbrief_parse_units_and_waypoints(self):
    p={'fetch':{'status':'Success'}, 'params':{'units':'kgs'},
       'general':{'costindex':'78'}, 'atc':{'callsign':'DLH2304'},
       'origin':{'icao_code':'EDDS'},'destination':{'icao_code':'EDDV'},
       'fuel':{'plan_ramp':'12634','plan_takeoff':'12260','enroute_burn':'4813','plan_landing':'7447'},
       'navlog':{'fix':[{'ident':'MASEK','pos_lat':'50.730','pos_long':'9.590','fuel_plan_onboard':'8315','stage':'CRZ'}, {'ident':'WERRA','pos_lat':'51.47','pos_long':'9.73','fuel_plan_onboard':'8100','stage':'DSC'}]},
       'files':{'directory':'https://www.simbrief.com/ofp/flightplans/','pdf':{'link':'myplan.pdf'}}}
    v=normalize_ofp(p)
    self.assertEqual(v['meta']['ofp_dest_efob_kg'],7447)
    self.assertEqual(v['meta']['flight'],'DLH2304')
    self.assertEqual(v['route_fixes'][0]['planned_kg'],8315)
    self.assertEqual(v['pdf_url'],'https://www.simbrief.com/ofp/flightplans/myplan.pdf')
    p['params']['units']='lbs'
    self.assertAlmostEqual(normalize_ofp(p)['meta']['ofp_trip_kg'],4813*.45359237,places=2)
  def test_simbrief_pdf_url_restriction(self):
    p={'files':{'directory':'https://evil.example/','pdf':{'link':'evil.pdf'}}}
    self.assertIsNone(normalize_ofp(p)['pdf_url'])
  def test_automatic_waypoint_match(self):
    lock=threading.RLock()
    data={'tracking_enabled':True,'route_fixes':[{'lat':48.1,'lon':9.1,'ident':'A','planned_kg':10000,'phase':'CLB'}, {'lat':48.3,'lon':9.2,'ident':'B','planned_kg':9500,'phase':'CLB'}], 'samples':[],'telemetry':[]}
    def load():return json.loads(json.dumps(data))
    def save(d):data.update(d)
    b=Bridge(load,save,lock)
    b._record({'lat':48.1001,'lon':9.1001,'fob_kg':9970,'ff1_kg_h':2000,'ff2_kg_h':2000,'altitude_ft':10000})
    self.assertEqual(len(data['samples']),1)
    self.assertAlmostEqual(data['samples'][0]['delta_kg'],-30)
    b._record({'lat':48.1001,'lon':9.1001,'fob_kg':9950})
    self.assertEqual(len(data['samples']),1)
    b._record({'lat':48.3001,'lon':9.2001,'fob_kg':9460})
    self.assertEqual(len(data['samples']),2)
  def test_pdf_and_zip_exports(self):
    state=json.loads(json.dumps(app.DEF))
    state['meta'].update({'flight':'LH2304','dep':'EDDS','arr':'EDDV'})
    state['samples']=[{'ident':'A','timestamp':1794070000,'actual_kg':9000.,'planned_kg':9500.,'delta_kg':-500.,'distance_nm':0.2},
                      {'ident':'B','timestamp':1794070500,'actual_kg':8100.,'planned_kg':8400.,'delta_kg':-300.,'distance_nm':0.3}]
    state['snapshots']=[{'phase':'Cruise','timestamp':'17:30 UTC','fms_efob_kg':'7700','ff1_kg_h':'3400','ff2_kg_h':'3350','note':'Measured value'}]
    pdf=app.make_report(state)
    self.assertTrue(pdf.startswith(b'%PDF'))
    with zipfile.ZipFile(io.BytesIO(app.make_bundle(state))) as z:
      self.assertIn('A350_Fuel_Evidence_Report.pdf',z.namelist())
      self.assertIn('waypoint_fuel_checkpoints.csv',z.namelist())

if __name__=='__main__': unittest.main()
