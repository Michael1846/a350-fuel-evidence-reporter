# SPDX-License-Identifier: AGPL-3.0-only
import json,sys,unittest, tempfile,base64
from pathlib import Path
from io import BytesIO
from unittest.mock import patch
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
from evidence_checklist import checklist
from telemetry_store import TelemetryStore

class WorkflowTests(unittest.TestCase):
  def state(self):return json.loads(json.dumps(app.DEF))
  def status(self,s,ident):
    w=checklist(s)
    for g in w['stages']:
      for v in g['items']:
        if v['id']==ident:return v['done']
    raise AssertionError(ident)
  def test_preflight_requires_real_screenshot_and_manual_pushback_value(self):
    s=self.state()
    s['case_types']=['ground_efob']
    s['meta'].update({'version':'1.2.8','live_time':'Yes','live_weather':'Yes','ofp_dest_efob_kg':'7447'})
    s['ofp']={'id':'dummy','original':'pdf'}
    self.assertFalse(self.status(s,'preflight_img'))
    self.assertFalse(self.status(s,'pushback'))
    s['evidence'].append({'id':'screen1','purpose':'preflight_prediction','phase':'Pushback'})
    s['snapshots'].append({'id':'obs1','phase':'Pushback','fms_efob_kg':'7300'})
    self.assertTrue(self.status(s,'preflight_img'))
    self.assertTrue(self.status(s,'pushback'))
    self.assertFalse(self.status(s,'landing'))
    s['snapshots'].append({'id':'obs2','phase':'Runway vacated','actual_fob_kg':'6850'})
    self.assertTrue(checklist(s)['ready'])
  def test_enroute_requires_two_distinct_types_of_image_and_autosave(self):
    s=self.state();s['case_types']=['enroute_efob']
    s['snapshots']=[{'id':'x','phase':'Cruise','fms_efob_kg':'7010'}]
    s['evidence']=[{'purpose':'preflight_prediction','phase':'Pushback'}, {'purpose':'fms_fuel_load','phase':'Cruise'}]
    self.assertTrue(self.status(s,'enroute_value'))
    self.assertTrue(self.status(s,'enroute_fms'))
    self.assertFalse(self.status(s,'enroute_ff'))
    self.assertFalse(self.status(s,'enroute_bin'))
    s['evidence'].append({'purpose':'engine_ff','phase':'Pushback'})
    self.assertFalse(self.status(s,'enroute_ff'))
    s['evidence'][-1]['phase']='Cruise'
    self.assertTrue(self.status(s,'enroute_ff'))
  def test_excessive_burn_images_must_link_to_same_observation(self):
    s=self.state();s['case_types']=['excessive_burn']
    s['snapshots']=[{'id':'a','issue_type':'excessive_burn','phase':'Climb','ff1_kg_h':'3300','note':'Sudden fuel flow peak at 12000 ft'}, {'id':'b','issue_type':'enroute_efob','phase':'Cruise'}]
    self.assertTrue(self.status(s,'burn_event'))
    s['evidence']=[{'id':'1','purpose':'engine_ff','observation_id':'b'}, {'id':'2','purpose':'fms_fuel_load','observation_id':'a'}]
    self.assertFalse(self.status(s,'burn_ff_img'))
    self.assertTrue(self.status(s,'burn_fms_img'))
    s['evidence'][0]['observation_id']='a'
    self.assertTrue(self.status(s,'burn_ff_img'))
  def test_screenshot_metadata_stored_and_report_pdf_renders(self):
    with tempfile.TemporaryDirectory() as tmp:
      from PIL import ImageDraw
      image=Image.new('RGB',(900,500),'white')
      d=ImageDraw.Draw(image);d.text((30,30),'SYNTHETIC SCREENSHOT — not A350 flight evidence',fill='black')
      b=BytesIO();image.save(b,format='PNG')
      with patch.object(app,'FILES',Path(tmp)),patch.object(app,'TELEM_STORE',TelemetryStore(Path(tmp)/'telemetry.csv')):
        item=app.upload('test.png',base64.b64encode(b.getvalue()).decode(),'screenshot','Pushback','17:00 UTC','Preflight','preflight_prediction','')
        self.assertEqual(item['purpose'],'preflight_prediction')
        s=self.state();s['evidence']=[item];s['case_types']=['ground_efob']
        s['snapshots']=[{'id':'x','issue_type':'ground_efob','phase':'Pushback','timestamp':'17:00 UTC','fms_efob_kg':'7000'}]
        pdf=app.make_report(s)
        self.assertTrue(pdf.startswith(b'%PDF-'))
        import fitz
        doc=fitz.open(stream=pdf,filetype='pdf');txt=' '.join(p.get_text() for p in doc)
        self.assertIn('Evidence checklist',txt)
        self.assertIn('preflight_prediction',txt)
        doc.close()
if __name__=='__main__':unittest.main()
