# SPDX-License-Identifier: AGPL-3.0-only
import io, json, tempfile, time, unittest, sys, zipfile
from pathlib import Path
from unittest.mock import patch
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
from evidence_capture import freeze_sim_context
from telemetry_store import TelemetryStore

class CaptureTests(unittest.TestCase):
    def test_fresh_position_and_age_recorded(self):
        now=1794067323.0
        status={'state':'connected','timestamp':now-2.1,'flight_status':'AIRBORNE','identity':{'title':'A350-900'},
                'data':{'lat':48.12345,'lon':9.56789,'altitude_ft':22500,'groundspeed_kt':360,'fob_kg':8100}}
        v=freeze_sim_context(status,now)
        self.assertEqual(v['telemetry_age_seconds'],2.1)
        self.assertEqual(v['lat'],48.12345)
        self.assertEqual(v['context_status'],'fresh_simconnect')
        self.assertIn('last polled',v['context_source'])

    def test_stale_gps_is_not_falsely_attached(self):
        status={'state':'connected','timestamp':100,'data':{'lat':48,'lon':9,'fob_kg':5000}}
        v=freeze_sim_context(status,120)
        self.assertIsNone(v['lat'])
        self.assertIsNone(v['fob_kg'])
        self.assertEqual(v['context_status'],'unavailable_or_stale')

    def test_http_capture_update_and_fms_reference(self):
        import threading, urllib.request
        from http.server import ThreadingHTTPServer
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);(base/'files').mkdir()
            (base/'case.json').write_text(json.dumps(app.DEF))
            b=io.BytesIO();Image.new('RGB',(600,350),'white').save(b,format='PNG')
            status={'state':'connected','timestamp':time.time()-1,'flight_status':'AIRBORNE',
                    'identity':{},'data':{'lat':52.1234,'lon':9.9876,'vertical_speed_fpm':-950,'altitude_ft':15000}}
            with patch.object(app,'DATA',base),patch.object(app,'FILES',base/'files'),\
                 patch.object(app,'STATE_PATH',base/'case.json'),patch.object(app,'CONFIG_PATH',base/'config.json'),\
                 patch.object(app,'TELEM_STORE',TelemetryStore(base/'data.csv')),patch.object(app.BRIDGE,'status',status),\
                 patch.object(app,'grab_screen',return_value=(b.getvalue(),(600,350))):
                http=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
                t=threading.Thread(target=http.serve_forever,daemon=True);t.start()
                url='http://127.0.0.1:'+str(http.server_address[1])
                def post(path,payload):
                    req=urllib.request.Request(url+path,json.dumps(payload).encode(),{'Content-Type':'application/json'})
                    with urllib.request.urlopen(req,timeout=5) as res:return json.load(res)
                try:
                    event=post('/api/capture-screenshot',{'mode':'foreground','purpose':'other','phase':'Auto'})['item']
                    self.assertEqual(event['phase'],'Descent')
                    self.assertIsNotNone(event['context']['lat'])
                    updated=post('/api/evidence-update',{'id':event['id'],'note':'FMS increased suddenly','purpose':'fms_fuel_load'})
                    self.assertEqual(updated['state']['evidence'][0]['note'],'FMS increased suddenly')
                    obs=post('/api/snapshot',{'issue_type':'enroute_efob','phase':'Descent',
                            'fms_efob_kg':'7100','reference_capture_id':event['id'],'note':'manual review'})
                    self.assertEqual(obs['state']['snapshots'][0]['lat'],52.1234)
                    self.assertEqual(obs['state']['snapshots'][0]['timestamp'],event['context']['event_time_utc'])
                    self.assertEqual(obs['state']['snapshots'][0]['fms_efob_kg'],'7100')
                finally:
                    http.shutdown();http.server_close();t.join(timeout=5)

    def test_capture_preserves_size_location_comment_and_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);(base/'files').mkdir()
            s=json.loads(json.dumps(app.DEF))
            s['route_fixes']=[{'ident':'MASEK','lat':50.0,'lon':9.2},{'ident':'WERRA','lat':51.0,'lon':9.2}]
            (base/'case.json').write_text(json.dumps(s))
            b=io.BytesIO();Image.new('RGB',(2800,1440),'white').save(b,format='PNG')
            mock_status={'state':'connected','timestamp':time.time()-1,'flight_status':'AIRBORNE',
                        'identity':{'title':'A350-900'},'data':{'lat':50.001,'lon':9.201,'altitude_ft':33000,
                        'fob_kg':8600,'ff1_kg_h':3300,'ff2_kg_h':3290,'groundspeed_kt':440}}
            with patch.object(app,'DATA',base),patch.object(app,'FILES',base/'files'),\
                 patch.object(app,'STATE_PATH',base/'case.json'),patch.object(app,'CONFIG_PATH',base/'config.json'),patch.object(app,'TELEM_STORE',TelemetryStore(base/'data.csv')),\
                 patch.object(app.BRIDGE,'status',mock_status),patch.object(app,'grab_screen',return_value=(b.getvalue(),(2800,1440))):
                item,state=app.capture_evidence('foreground','other','Cruise','','')
                self.assertEqual(item['context']['nearest_ofp_waypoint'],'MASEK')
                self.assertAlmostEqual(item['context']['altitude_ft'],33000)
                self.assertEqual(item['context']['lat'],50.001)
                self.assertTrue(item['remark_pending'])
                # In original resolution for evidence (unlike low-quality 2560px thumbnails)
                self.assertEqual(Image.open(app.file_for(item)).size,(2800,1440))
                state['evidence'][0]['note']='Unusually high FF: comparison with FMS'
                app.save(state)
                pdf=app.make_report(state)
                self.assertTrue(pdf.startswith(b'%PDF'))
                import fitz
                doc=fitz.open(stream=pdf,filetype='pdf')
                extracted=' '.join(page.get_text() for page in doc)
                self.assertIn('Unusually high FF',extracted)
                self.assertIn('33000',extracted)
                self.assertIn('MASEK',extracted)
                doc.close()
                pack=zipfile.ZipFile(io.BytesIO(app.make_bundle(state)))
                attached=json.loads(pack.read('screenshot_contexts.json'))
                self.assertEqual(attached[0]['context']['lat'],50.001)
                self.assertIn('screenshots/screenshot_01.png',pack.namelist())
                pack.close()

if __name__=='__main__':unittest.main()
