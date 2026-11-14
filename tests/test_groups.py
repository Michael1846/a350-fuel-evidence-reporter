# SPDX-License-Identifier: AGPL-3.0-only
import base64, io, json, tempfile, time, unittest, sys, zipfile, threading, urllib.request
from pathlib import Path
from unittest.mock import patch
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
from telemetry_store import TelemetryStore
from evidence_groups import new_group, assign_screenshot, reorder_screenshot, ordered_screenshots, evidence_audit

class GroupV06Tests(unittest.TestCase):
    def png(self,n):
        b=io.BytesIO();im=Image.new('RGB',(600,340),((150+n*15)%255,225,210));im.save(b,'PNG');return b.getvalue()
    def state(self):return json.loads(json.dumps(app.DEF))

    def test_three_independently_timestamped_contexts_reordered_and_exported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'files').mkdir()
            s=self.state();g=new_group('EFOB transition at MASEK','enroute_efob','Compare screenshot 1 to 2 to 3: EFOB drops at the waypoint transition.')
            s['groups'].append(g)
            with patch.object(app,'FILES',root/'files'),patch.object(app,'TELEM_STORE',TelemetryStore(root/'telemetry.csv')):
                for idx,(lat,fob,ff) in enumerate([(50.0,9000,6200),(50.12,8850,6600),(50.21,8720,7200)],1):
                    item=app.upload(f'moment{idx}.png',base64.b64encode(self.png(idx)).decode(),'screenshot','Cruise',f'2026-11-07T17:00:0{idx}Z','', 'fms_fuel_load' if idx%2 else 'engine_ff','',g['id'])
                    item['context']={'lat':lat,'lon':9.12,'altitude_ft':33000,'fob_kg':fob,'ff1_kg_h':ff/2,'ff2_kg_h':ff/2}
                    s['evidence'].append(item);assign_screenshot(s,item['id'],g['id'])
                ids=[x['id'] for x in s['evidence']]
                reorder_screenshot(s,g['id'],ids[2],-1)
                self.assertEqual(g['screenshot_ids'],[ids[0],ids[2],ids[1]])
                self.assertEqual([x['context']['fob_kg'] for x in ordered_screenshots(s,g)],[9000,8720,8850])
                pdf=app.make_report(s)
                self.assertTrue(pdf.startswith(b'%PDF-'))
                import fitz
                d=fitz.open(stream=pdf,filetype='pdf');txt='\n'.join(page.get_text() for page in d)
                self.assertIn('Compare screenshot 1 to 2 to 3',txt)
                self.assertLess(txt.index('Screenshot 1'),txt.index('Screenshot 2'))
                self.assertLess(txt.index('Screenshot 2'),txt.index('Screenshot 3'))
                self.assertLess(txt.index('8720'),txt.index('8850'))
                d.close()
                z=zipfile.ZipFile(io.BytesIO(app.make_bundle(s)))
                self.assertEqual(len([n for n in z.namelist() if n.startswith('screenshots/')]),3)
                meta=json.loads(z.read('screenshot_contexts.json'))
                self.assertEqual([x['context']['lat'] for x in meta],[50.0,50.12,50.21])
                grouped=json.loads(z.read('event_groups.json'))
                self.assertEqual(grouped['groups'][0]['screenshot_ids'],[ids[0],ids[2],ids[1]])
                z.close()

    def test_multiple_autosaves_and_missing_autosaves_are_advisory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'files').mkdir()
            s=self.state();g=new_group('High fuel flow','excessive_burn','unexpected fuel flow during climb');s['groups'].append(g)
            s['snapshots'].append({'id':'obs','group_id':g['id'],'ff1_kg_h':'4300','note':'Climb spike'})
            self.assertTrue(evidence_audit(s)[0]['export_allowed'])
            self.assertIn('ois_autosave',[x['id'] for x in evidence_audit(s)[0]['requirements'] if not x['done']])
            with patch.object(app,'FILES',root/'files'),patch.object(app,'TELEM_STORE',TelemetryStore(root/'telemetry.csv')):
                a=[]
                for i in range(2):
                    raw=b'FAKE-OIS-'+bytes([i])
                    item=app.upload(f'save{i}.bin',base64.b64encode(raw).decode(),'bin',group_id=g['id']);s['autosaves'].append(item);a.append(raw)
                z=zipfile.ZipFile(io.BytesIO(app.make_bundle(s)))
                names=sorted(x for x in z.namelist() if x.startswith('ois_autosaves/'))
                self.assertEqual(len(names),2)
                self.assertEqual([z.read(x) for x in names],a)
                self.assertTrue(app.make_report(s).startswith(b'%PDF'))
                z.close()

    def test_group_separation_does_not_credit_other_groups_files(self):
        s=self.state();g1=new_group('Before waypoint','enroute_efob');g2=new_group('After waypoint','enroute_efob')
        s['groups']=[g1,g2]
        s['snapshots']=[{'id':'obs1','group_id':g1['id'],'fms_efob_kg':'7500'},{'id':'obs2','group_id':g2['id'],'fms_efob_kg':'6500'}]
        s['evidence']=[{'id':'img1','group_id':g1['id'],'purpose':'fms_fuel_load'},{'id':'img2','group_id':g2['id'],'purpose':'engine_ff'}]
        g1['screenshot_ids']=['img1'];g2['screenshot_ids']=['img2']
        s['autosaves']=[{'id':'x.bin','group_id':g1['id']}]
        report=evidence_audit(s)
        check1={v['id']:v['done'] for v in report[0]['requirements']}
        check2={v['id']:v['done'] for v in report[1]['requirements']}
        self.assertTrue(check1['fms_screen']);self.assertFalse(check1['engine_ff_screen'])
        self.assertFalse(check2['fms_screen']);self.assertTrue(check2['engine_ff_screen'])
        self.assertTrue(check1['ois_autosave']);self.assertFalse(check2['ois_autosave'])
        self.assertTrue(all(g['export_allowed'] for g in report))

    def test_hotkey_default_group_preserves_each_simconnect_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'files').mkdir()
            s=self.state();g=new_group('EFOB changing at fix','enroute_efob','Before to after');s['groups']=[g]
            s['active_capture_group_id']=g['id']
            (root/'case.json').write_text(json.dumps(s))
            status={'state':'connected','timestamp':time.time()-0.5,'flight_status':'AIRBORNE','data':{'lat':50.0,'lon':9.1,'altitude_ft':33000,'fob_kg':8500,'ff1_kg_h':3100,'ff2_kg_h':3095}}
            with patch.object(app,'DATA',root),patch.object(app,'STATE_PATH',root/'case.json'),patch.object(app,'FILES',root/'files'),patch.object(app,'CONFIG_PATH',root/'config.json'),patch.object(app.BRIDGE,'status',status),patch.object(app,'grab_screen',return_value=(self.png(2),(600,340))):
                first,_=app.capture_evidence()
                status['data']['lat']=50.2;status['data']['fob_kg']=8210;status['timestamp']=time.time()-0.5
                second,_=app.capture_evidence()
                actual=app.load()
                self.assertEqual(actual['groups'][0]['screenshot_ids'],[first['id'],second['id']])
                self.assertEqual(actual['evidence'][0]['context']['lat'],50.0)
                self.assertEqual(actual['evidence'][1]['context']['lat'],50.2)
                self.assertEqual(actual['evidence'][0]['context']['fob_kg'],8500)
                self.assertEqual(actual['evidence'][1]['context']['fob_kg'],8210)

    def test_legacy_v05_bin_migrated_without_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);state=self.state();state['bin']={'id':'legacy.bin','original':'save.bin'}
            del state['autosaves'];del state['groups']
            (root/'case.json').write_text(json.dumps(state))
            with patch.object(app,'DATA',root),patch.object(app,'STATE_PATH',root/'case.json'),patch.object(app,'FILES',root/'files'),patch.object(app,'CONFIG_PATH',root/'config.json'):
                out=app.load()
                self.assertEqual(out['autosaves'][0]['id'],'legacy.bin')
                self.assertEqual(out['groups'],[])

    def test_local_http_endpoints_create_link_reorder_and_export_without_bin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'files').mkdir();(root/'case.json').write_text(json.dumps(self.state()))
            with patch.object(app,'DATA',root),patch.object(app,'FILES',root/'files'),patch.object(app,'STATE_PATH',root/'case.json'),patch.object(app,'CONFIG_PATH',root/'config.json'),patch.object(app,'TELEM_STORE',TelemetryStore(root/'telemetry.csv')):
                http=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
                thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
                url='http://127.0.0.1:'+str(http.server_address[1])
                def post(path,obj):
                    req=urllib.request.Request(url+path,json.dumps(obj).encode(),{'Content-Type':'application/json'})
                    with urllib.request.urlopen(req,timeout=10) as res:return json.load(res)
                try:
                    group=post('/api/group-create',{'title':'Before / after TOD','issue_type':'enroute_efob','remark':'Screen 1 to 2 to 3'})['group']
                    gid=group['id']
                    post('/api/active-capture-group',{'group_id':gid})
                    for n in range(3):
                        post('/api/attachment',{'category':'screenshot','name':f'{n}.png','data':base64.b64encode(self.png(n)).decode(),
                             'purpose':'fms_fuel_load','phase':'Cruise','timestamp':f'2026-11-07T17:00:0{n}Z','group_id':gid})
                    s=app.load();ids=s['groups'][0]['screenshot_ids']
                    self.assertEqual(len(ids),3)
                    post('/api/group-move-screenshot',{'group_id':gid,'screenshot_id':ids[2],'direction':-1})
                    post('/api/group-update',{'id':gid,'remark':'Waypoints cause FMS EFOB step change'})
                    with urllib.request.urlopen(url+'/api/group-audit',timeout=10) as res:audit=json.load(res)
                    self.assertEqual(audit[0]['count_screenshots'],3)
                    with urllib.request.urlopen(url+'/api/export.pdf',timeout=10) as res:pdf=res.read()
                    self.assertTrue(pdf.startswith(b'%PDF'))
                    with urllib.request.urlopen(url+'/api/export.zip',timeout=10) as res:pkg=res.read()
                    self.assertTrue(zipfile.is_zipfile(io.BytesIO(pkg)))
                    post('/api/group-assign-screenshot',{'group_id':'','screenshot_id':ids[0]})
                    self.assertEqual(app.load()['evidence'][0]['group_id'],'')
                finally:
                    http.shutdown();http.server_close();thread.join(timeout=5)

if __name__=='__main__':unittest.main()
